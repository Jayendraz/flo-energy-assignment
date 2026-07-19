"""Renders MeterReading records as batched upsert INSERT statements."""

from typing import IO, Iterable

from nem12_to_sql.models import MeterReading

TABLE = "meter_readings"


def generate_insert_statements(
    readings: Iterable[MeterReading], out: IO[str], batch_size: int = 1000, no_upsert: bool = False
) -> int:
    """Write batched INSERT statements to `out`. Returns the number of rows written."""
    batch: list[MeterReading] = []
    total = 0

    for reading in readings:
        batch.append(reading)
        if len(batch) == batch_size:
            _write_batch(batch, out, no_upsert)
            total += len(batch)
            batch.clear()

    if batch:
        _write_batch(batch, out, no_upsert)
        total += len(batch)

    return total


def _write_batch(batch: list[MeterReading], out: IO[str], no_upsert: bool = False) -> None:
    out.write(f'INSERT INTO {TABLE} (nmi, "timestamp", consumption) VALUES\n')
    rows = ",\n".join(f"  ({_sql_row(reading)})" for reading in batch)
    out.write(rows)
    if no_upsert:
        out.write(";\n")
    else:
        out.write(
            '\nON CONFLICT (nmi, "timestamp") DO UPDATE SET consumption = EXCLUDED.consumption;\n'
        )


def _sql_row(reading: MeterReading) -> str:
    nmi_literal = _sql_string(reading.nmi)
    timestamp_literal = _sql_string(reading.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
    return f"{nmi_literal}, {timestamp_literal}, {reading.consumption}"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
