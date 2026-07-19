from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MeterReading:
    """One row destined for meter_readings: (nmi, timestamp) is unique."""

    nmi: str
    timestamp: datetime
    consumption: Decimal


@dataclass(slots=True)
class NMIBlock:
    """Parsed 200-record context that following 300-records belong to."""

    nmi: str
    interval_minutes: int
