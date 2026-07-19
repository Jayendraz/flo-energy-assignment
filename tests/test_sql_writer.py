import io
from datetime import datetime
from decimal import Decimal

from nem12_to_sql.models import MeterReading
from nem12_to_sql.sql_writer import generate_insert_statements

# ---------- Helper Functions ---------- #

def reading(nmi="NEM1201009", ts=datetime(2005, 3, 1, 0, 30), value="0.461"):
    return MeterReading(nmi=nmi, timestamp=ts, consumption=Decimal(value))

# ---------- Tests Functions ---------- #

def test_generate_single_insert_statement_format():
    out = io.StringIO()
    count = generate_insert_statements([reading()], out, batch_size=1000)

    sql = out.getvalue()
    assert count == 1
    assert 'INSERT INTO meter_readings (nmi, "timestamp", consumption) VALUES' in sql
    assert "('NEM1201009', '2005-03-01 00:30:00', 0.461)" in sql
    assert 'ON CONFLICT (nmi, "timestamp") DO UPDATE SET consumption = EXCLUDED.consumption;' in sql


def test_generate_insert_statements_splits_into_batches():
    # Arrange
    readings = [reading(ts=datetime(2005, 3, 1, i, 0)) for i in range(5)]
    out = io.StringIO()
    # Action
    count = generate_insert_statements(readings, out, batch_size=2)
    # Assert
    sql = out.getvalue()
    assert count == 5
    assert sql.count("INSERT INTO meter_readings") == 3  # 2 + 2 + 1


def test_nmi_single_quote_is_escaped():
    # Arrange
    out = io.StringIO()
    # Action
    generate_insert_statements([reading(nmi="O'BRIEN01")], out, batch_size=1000)
    # Assert
    assert "'O''BRIEN01'" in out.getvalue()


def test_no_sql_output_for_empty_readings():
    out = io.StringIO()
    count = generate_insert_statements([], out, batch_size=1000)
    assert count == 0
    assert out.getvalue() == ""


def test_no_upsert_generates_simple_insert_without_conflict_clause_when_no_upsert_is_true():
    out = io.StringIO()
    count = generate_insert_statements([reading()], out, batch_size=1000, no_upsert=True)

    sql = out.getvalue()
    assert count == 1
    assert "('NEM1201009', '2005-03-01 00:30:00', 0.461);\n" in sql
    assert "ON CONFLICT" not in sql


def test_no_upsert_generates_simple_insert_with_conflict_clause_when_no_upsert_is_false():
    out = io.StringIO()
    count = generate_insert_statements([reading()], out, batch_size=1000, no_upsert=False)

    sql = out.getvalue()
    assert count == 1
    assert "('NEM1201009', '2005-03-01 00:30:00', 0.461)" in sql
    assert (
        'ON CONFLICT (nmi, "timestamp") DO UPDATE SET consumption = EXCLUDED.consumption;'
        in sql
    )
    assert not sql.rstrip().endswith(");")
