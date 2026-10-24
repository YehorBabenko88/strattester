"""Conservative detection of ambiguous point-in-time market revisions.

Reject multiple versions of one event instead of silently selecting the
latest revision. A future audited schema may define explicit revision IDs.
"""
from collections.abc import Mapping, Sequence


class RevisionConflictError(ValueError):
    pass


def reject_ambiguous_revisions(
    rows: Sequence[Mapping],
    *,
    event_field: str = "event_time",
    ingestion_field: str = "ingestion_time",
) -> None:
    seen = {}
    for row in rows:
        event = row[event_field]
        ingestion = row[ingestion_field]
        if type(event) is not int or type(ingestion) is not int:
            raise RevisionConflictError("Invalid revision timestamps")
        if event in seen:
            raise RevisionConflictError(
                "Multiple versions of event timestamp; explicit revision contract required"
            )
        seen[event] = ingestion
