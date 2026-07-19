"""Streaming NEM12 parser.

Reads a NEM12 file one line at a time and yields MeterReading records. Memory
use is bounded by the current 200-record's context (NMI + interval length),
not by file size.
"""

import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import IO, Iterator

from nem12_to_sql.exceptions import NEM12ParseError
from nem12_to_sql.models import MeterReading, NMIBlock

logger = logging.getLogger(__name__)

NMI_RE = re.compile(r"^[A-Z0-9]{1,10}$")  # only alphnumeric is allowed for NMI
MINUTES_PER_DAY = 24 * 60

START_RECORD_TYPE = "100"
INTERVAL_RECORD_TYPE = "200"
CONSUMPTION_RECORD_TYPE = "300"
IGNORED_RECORD_TYPES = "500"
END_RECORD_TYPE = "900"


class NEM12Parser:
    def __init__(self, lenient: bool = False):
        self.lenient = lenient

    def parse(self, fileobj: IO[str]) -> Iterator[MeterReading]:
        current_nmi_block: NMIBlock | None = None

        for line_no, raw_line in enumerate(fileobj, start=1):

            # Sanitize the input stream by removing any trailing newlines or carriage in each line and skipping empty lines
            line = raw_line.rstrip("\r\n")
            if not line:
                continue

            fields = line.split(",")
            record_type = fields[0].strip()

            if record_type == START_RECORD_TYPE:
                continue

            if record_type == INTERVAL_RECORD_TYPE:
                current_nmi_block = self._parse_200(fields, line_no, line)
                continue

            if record_type == CONSUMPTION_RECORD_TYPE:
                if current_nmi_block is None:
                    raise NEM12ParseError(
                        line_no, line, "300 record with no preceding 200 record"
                    )
                try:
                    yield from self._parse_300(fields, line_no, line, current_nmi_block)
                except NEM12ParseError:
                    if self.lenient:
                        logger.warning("skipping malformed 300 record at line %d", line_no)
                        continue
                    raise
                continue

            if record_type == IGNORED_RECORD_TYPES:
                current_nmi_block = None
                continue

            if record_type == END_RECORD_TYPE:
                return

            raise NEM12ParseError(line_no, line, f"unrecognized record type {record_type!r}")


    def _parse_200(self, fields: list[str], line_no: int, line: str) -> NMIBlock:
        if len(fields) < 9:
            raise NEM12ParseError(line_no, line, "200 record has too few fields")

        nmi = fields[1].strip()
        if not NMI_RE.match(nmi):
            raise NEM12ParseError(line_no, line, f"invalid NMI {nmi!r}")

        try:
            interval_minutes = int(fields[8].strip())
        except ValueError:
            raise NEM12ParseError(line_no, line, f"invalid interval length {fields[8]!r}") from None

        if interval_minutes <= 0 or MINUTES_PER_DAY % interval_minutes != 0:
            raise NEM12ParseError(
                line_no, line, f"interval length {interval_minutes} doesn't divide a day"
            )

        return NMIBlock(nmi=nmi, interval_minutes=interval_minutes)


    def _parse_300(
        self, fields: list[str], line_no: int, line: str, nmi_block: NMIBlock | None
    ) -> Iterator[MeterReading]:
        if nmi_block is None:
            raise NEM12ParseError(line_no, line, "300 record with no preceding 200 record")

        if len(fields) < 2:
            raise NEM12ParseError(line_no, line, "300 record has too few fields")

        try:
            interval_date = datetime.strptime(fields[1].strip(), "%Y%m%d")
        except ValueError:
            raise NEM12ParseError(line_no, line, f"invalid interval date {fields[1]!r}") from None

        expected_count = MINUTES_PER_DAY // nmi_block.interval_minutes
        values = fields[2 : 2 + expected_count]
        if len(values) != expected_count:
            raise NEM12ParseError(
                line_no,
                line,
                f"expected {expected_count} interval values, found {len(values)}",
            )

        yield from self._parse_interval_values(
            values, interval_date, nmi_block, line_no, line
        )


    def _parse_interval_values(
        self,
        values: list[str],
        interval_date: datetime,
        nmi_block: NMIBlock,
        line_no: int,
        line: str,
    ) -> Iterator[MeterReading]:
        for i, raw_value in enumerate(values, start=1):
            try:
                consumption = Decimal(raw_value)
            except InvalidOperation:
                raise NEM12ParseError(
                    line_no, line, f"invalid consumption value {raw_value!r}"
                ) from None

            timestamp = interval_date + timedelta(minutes=nmi_block.interval_minutes * i)
            yield MeterReading(nmi=nmi_block.nmi, timestamp=timestamp, consumption=consumption)
