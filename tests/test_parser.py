import io
import logging
from datetime import datetime
from decimal import Decimal

import pytest

from nem12_to_sql.exceptions import NEM12ParseError
from nem12_to_sql.parser import NEM12Parser

HEADER = "100,NEM12,200506081149,UNITEDDP,NEMMCO\n"

# ---------- Helper Functions ---------- #

def parse(input_csv_text, lenient=False):
    return NEM12Parser(lenient=lenient).parse(io.StringIO(input_csv_text))


def make_200(nmi="NEM1201009", interval_minutes=30):
    return f"200,{nmi},E1E2,1,E1,N1,01009,kWh,{interval_minutes},20050610\n"

def make_300(date="20050301", interval_minutes=30):
    n = 24 * 60 // interval_minutes
    values = [f"{i / 10:.3f}" for i in range(1, n + 1)]
    assert len(values) == n
    return f"300,{date}," + ",".join(values) + ",A,,,20050310121004,20050310182204\n"

def make_500():
    return "500,O,S01009,20050310121004,\n"


# ---------- Tests Functions ---------- #

def test_parse_single_interval_block():
    input_csv = HEADER + \
        make_200(nmi="NEM1201009") + \
        make_300() + \
        "900\n"

    readings = list(parse(input_csv))

    assert len(readings) == 48
    assert readings[0].nmi == "NEM1201009"
    assert readings[0].timestamp == datetime(2005, 3, 1, 0, 30)
    assert readings[0].consumption == Decimal("0.100")
    assert readings[12].consumption == Decimal("1.300")

def test_parse_multiple_interval_blocks():
    # Arrange
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        make_300() + \
        make_300(date="20050302") + \
        make_500() + \
        make_200(nmi="NEM1201010") + \
        make_300() + \
        make_500() + \
        "900\n"
    # Action
    readings = list(parse(input_csv_text))
    # Assert
    assert len(readings) == 144
    assert readings[0].nmi == "NEM1201009"
    assert readings[0].timestamp == datetime(2005, 3, 1, 0, 30)
    assert readings[0].consumption == Decimal("0.100")
    assert readings[12].consumption == Decimal("1.300")
    assert readings[96].nmi == "NEM1201010"
    assert readings[96].timestamp == datetime(2005, 3, 1, 0, 30)
    assert readings[96].consumption == Decimal("0.100")


@pytest.mark.parametrize("lenient", [False, True])
def test_300_after_500_without_200_raises_parse_error(lenient):
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        make_300() + \
        make_500() + \
        make_300(date="20050302") + \
        "900\n"

    with pytest.raises(NEM12ParseError, match="300 record with no preceding 200 record"):
        list(parse(input_csv_text, lenient=lenient))


def test_last_interval_rolls_over_to_next_day_midnight():
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        make_300() + \
        "900\n"
    readings = list(parse(input_csv_text))
    assert readings[-1].timestamp == datetime(2005, 3, 2, 0, 0)


def test_parser_stops_at_900_record():
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        make_300() + \
        "900\n" + \
        "not,a,valid,record\n"
    readings = list(parse(input_csv_text))
    assert len(readings) == 48  # the junk line after 900 must never be reached


def test_500_record_is_ignored():
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        make_300() + \
        make_500() + \
        "900\n"
    readings = list(parse(input_csv_text))
    assert len(readings) == 48


def test_unrecognized_record_type_raise_parse_error():
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        make_300() + \
        "999,bogus\n" + \
        "900\n"
    with pytest.raises(NEM12ParseError):
        list(parse(input_csv_text))

def test_interval_count_mismatch_raises_in_strict_mode():
    bad_300 = "300,20050301," + ",".join(["0"] * 20) + ",A,,,20050310121004,\n"
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        bad_300 + \
        "900\n"
    with pytest.raises(NEM12ParseError):
        list(parse(input_csv_text))


def test_interval_count_mismatch_skipped_in_lenient_mode(caplog):
    bad_300 = "300,20050301," + ",".join(["0"] * 20) + ",A,,,20050310121004,\n"
    input_csv_text = HEADER + \
        make_200(nmi="NEM1201009") + \
        bad_300 + \
        "900\n"

    with caplog.at_level(logging.WARNING, logger="nem12_to_sql.parser"):
        readings = list(parse(input_csv_text, lenient=True))

    assert len(readings) == 0
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert caplog.records[0].name == "nem12_to_sql.parser"
    assert caplog.records[0].getMessage() == "skipping malformed 300 record at line 3"
