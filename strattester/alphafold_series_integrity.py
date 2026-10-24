"""Strict validation of one already bounded, point-in-time bar series.

No resampling, forward filling, silent deduplication or database writes.
Timestamp units and interval must be supplied by an audited caller.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence


class DataIntegrityError(ValueError):
    """An ML dataset is not safe to consume."""


def validate_regular_series(
    rows: Sequence[Mapping],
    *,
    interval: int,
    event_field: str = "event_time",
    ingestion_field: str = "ingestion_time",
    knowledge_cutoff: int,
    expected_start: int | None = None,
    expected_end: int | None = None,
) -> None:
    """Reject gaps, duplicates, out-of-order bars and future observations.

    The interval and timestamps must be expressed in the same unit.
    An empty series is invalid; completeness is checked against optional
    inclusive start/end bounds. Intended for regular bars, not trade ticks.
    """
    if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
        raise ValueError("interval must be a positive integer")
    if isinstance(knowledge_cutoff, bool) or not isinstance(knowledge_cutoff, int):
        raise ValueError("knowledge_cutoff must be an integer")
    for name, bound in (("expected_start", expected_start), ("expected_end", expected_end)):
        if bound is not None and (type(bound) is not int or bound < 0):
            raise ValueError(f"{name} must be a nonnegative integer")
    if expected_start is not None and expected_end is not None and expected_start > expected_end:
        raise ValueError("expected_start exceeds expected_end")
    if not rows:
        raise DataIntegrityError("Empty time series")
    previous = None
    for row in rows:
        event = row[event_field]
        ingestion = row[ingestion_field]
        if any(isinstance(t, bool) or not isinstance(t, int) for t in (event, ingestion)):
            raise DataIntegrityError("Non-integer timestamps")
        if event < 0 or ingestion < 0:
            raise DataIntegrityError("Negative event or ingestion timestamp")
        if event > knowledge_cutoff or ingestion > knowledge_cutoff:
            raise DataIntegrityError("Future event or ingestion")
        if previous is not None and event - previous != interval:
            raise DataIntegrityError("Duplicate, unordered, or missing bar")
        previous = event
    if expected_start is not None and rows[0][event_field] != expected_start:
        raise DataIntegrityError("Missing initial bar")
    if expected_end is not None and previous != expected_end:
        raise DataIntegrityError("Missing final bar")
