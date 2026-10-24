"""Fail-closed read-only SQLite point-in-time market data adapter.

This module intentionally does not infer source schemas or quality semantics.
A caller must supply an audited column mapping and an eligibility predicate.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterator


@dataclass(frozen=True)
class SQLiteSource:
    path: Path
    table: str
    instrument: str = "instrument"
    timeframe: str = "timeframe"
    market_type: str = "market_type"
    event_time: str = "event_time"
    ingestion_time: str = "ingestion_time"
    quality_status: str = "quality_status"
    eligible: str = "eligible"
    watermark: str = "watermark"


def _identifier(value: str) -> str:
    if not value or not (value[0].isalpha() or value[0] == "_") or not all(
        c.isalnum() or c == "_" for c in value
    ):
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return '"' + value + '"'


def point_in_time_rows(
    source: SQLiteSource,
    *,
    instrument: str,
    timeframe: str,
    market_type: str,
    event_cutoff: int,
    knowledge_cutoff: int,
    accepted_quality: str,
) -> Iterator[dict]:
    """Read one SQLite snapshot, filtering by both market and knowledge time.

    Cutoffs must use the exact timestamp unit and convention of the audited
    source schema. This adapter does not convert timestamps or merge shards.
    """
    columns = {
        name: _identifier(getattr(source, name))
        for name in (
            "table", "instrument", "timeframe", "market_type", "event_time",
            "ingestion_time", "quality_status", "eligible", "watermark"
        )
    }
    uri = source.path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        q = columns
        statement = f"""
            SELECT * FROM {q['table']}
            WHERE {q['instrument']} = ?
              AND {q['timeframe']} = ?
              AND {q['market_type']} = ?
              AND {q['event_time']} <= ?
              AND {q['ingestion_time']} <= ?
              AND {q['watermark']} >= {q['event_time']}
              AND {q['quality_status']} = ?
              AND {q['eligible']} = 1
            ORDER BY {q['event_time']}, {q['ingestion_time']}
        """
        for row in connection.execute(
            statement,
            (instrument, timeframe, market_type, event_cutoff,
             knowledge_cutoff, accepted_quality),
        ):
            yield dict(row)
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
