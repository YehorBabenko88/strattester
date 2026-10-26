"""Independent signed funding event oracle, separate from flat stress costs.

This is an accounting reference only, not a portfolio/exchange simulator.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class FundingEvent:
    instrument: str
    timestamp_ns: int
    rate: float

def funding_cashflow(position, start_ns, end_ns, instrument, events):
    """Positive funding rate: long pays and short receives, per unit notional.

    Include events strictly after entry and through exit: (start, end].
    """
    if type(position) is not int or position not in (-1, 0, 1):
        raise ValueError("invalid position")
    if any(type(t) is not int or t < 0 for t in (start_ns, end_ns)) or end_ns <= start_ns:
        raise ValueError("invalid interval")
    if not isinstance(instrument, str) or not instrument:
        raise ValueError("invalid instrument")
    seen = set()
    result = 0.
    for event in events:
        if not isinstance(event, FundingEvent) or not event.instrument:
            raise ValueError("invalid funding event")
        if type(event.timestamp_ns) is not int or event.timestamp_ns < 0 or type(event.rate) not in (int, float) or not math.isfinite(event.rate):
            raise ValueError("invalid funding event fields")
        key = (event.instrument, event.timestamp_ns)
        if key in seen:
            raise ValueError("duplicate funding event")
        seen.add(key)
        if event.instrument == instrument and start_ns < event.timestamp_ns <= end_ns:
            result -= position * event.rate
    if not math.isfinite(result):
        raise ValueError("nonfinite funding result")
    return result
