"""Strict experimental composition of read-only SQLite and integrity gates.

Not a Grid schema adapter. The source mapping, timestamp units and interval
must be independently verified before enabling this pipeline for research.
"""
from __future__ import annotations

from .alphafold_data_sync import SQLiteSource, bounded_point_in_time_rows
from .alphafold_series_integrity import validate_regular_series


def load_verified_regular_bars(
    source: SQLiteSource,
    *,
    instrument: str,
    timeframe: str,
    market_type: str,
    event_cutoff: int,
    knowledge_cutoff: int,
    accepted_quality: str,
    interval: int,
    expected_start: int,
    max_rows: int,
) -> tuple[dict, ...]:
    """Return bars only if the entire requested range passes validation."""
    if type(expected_start) is not int or expected_start < 0:
        raise ValueError("expected_start must be a nonnegative integer")
    if expected_start > event_cutoff:
        raise ValueError("expected_start exceeds event_cutoff")
    if type(interval) is not int or interval <= 0:
        raise ValueError("interval must be positive")
    if (event_cutoff - expected_start) % interval:
        raise ValueError("Requested range not aligned to interval")
    rows = bounded_point_in_time_rows(
        source, instrument=instrument, timeframe=timeframe,
        market_type=market_type, event_cutoff=event_cutoff,
        knowledge_cutoff=knowledge_cutoff, accepted_quality=accepted_quality,
        max_rows=max_rows,
    )
    validate_regular_series(
        rows, interval=interval, knowledge_cutoff=knowledge_cutoff,
        expected_start=expected_start, expected_end=event_cutoff,
        event_field=source.event_time, ingestion_field=source.ingestion_time,
    )
    return rows
