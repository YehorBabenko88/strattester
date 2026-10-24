"""Conservative cross-source snapshot manifest validation.

This is a coordination contract, NOT a distributed transaction or proof
of source completeness. The producer must attest each source independently.
"""
from dataclasses import dataclass


class SnapshotContractError(ValueError):
    pass


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    snapshot_id: str
    schema_version: str
    event_watermark: int
    knowledge_cutoff: int
    dataset_sha256: str


def validate_snapshot_manifest(
    sources: tuple[SourceSnapshot, ...],
    *,
    required_source_ids: frozenset[str],
    expected_schema_version: str,
    event_cutoff: int,
    knowledge_cutoff: int,
) -> None:
    """Fail closed on missing, duplicate, stale or inconsistent attestations."""
    if not sources or not required_source_ids:
        raise SnapshotContractError("Empty manifest or source requirements")
    if any(type(t) is not int or t < 0 for t in (event_cutoff, knowledge_cutoff)):
        raise SnapshotContractError("Invalid cutoff")
    ids = [s.source_id for s in sources]
    if len(ids) != len(set(ids)) or set(ids) != required_source_ids:
        raise SnapshotContractError("Missing, extra or duplicate sources")
    for s in sources:
        if not s.snapshot_id or s.schema_version != expected_schema_version:
            raise SnapshotContractError("Snapshot identity or schema mismatch")
        if type(s.event_watermark) is not int or s.event_watermark < event_cutoff:
            raise SnapshotContractError("Insufficient event watermark")
        if type(s.knowledge_cutoff) is not int or s.knowledge_cutoff != knowledge_cutoff:
            raise SnapshotContractError("Inconsistent knowledge cutoff")
        if len(s.dataset_sha256) != 64 or any(c not in "0123456789abcdef" for c in s.dataset_sha256):
            raise SnapshotContractError("Invalid SHA256 digest")
