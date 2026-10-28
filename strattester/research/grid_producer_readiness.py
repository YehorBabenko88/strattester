"""Pinned Grid source audit only; never a producer receipt or database exporter.

The inspected implementation cannot reconstruct first knowledge or overwritten
versions. Matching its source bytes confirms the scope of this audit, not native
producer ownership, physical schema state, or deployment readiness.
"""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import asdict, dataclass
import hashlib

GRID_SOURCE_COMMIT = 'd537d525296ef34f727996e240ae6c60102c6082'


@dataclass(frozen=True)
class SourceReceipt:
    path: str
    sha256: str
    byte_count: int


@dataclass(frozen=True)
class GridReadiness:
    source_commit: str
    source_receipts: tuple[SourceReceipt, ...]
    missing_facts: tuple[str, ...]
    status: str = 'BLOCKED'
    eligible: bool = False
    evidence_kind: str = 'PINNED_SOURCE_INSPECTION'

    def to_dict(self):
        return asdict(self)


_RECEIPTS = (
    SourceReceipt('grid/db.py', '5eb11360921800d12eb6ba4f62d4d034dc084c5406d37a30784d98ec3a588f1c', 3238),
    SourceReceipt('grid/migrations.py', 'b65cf37d0016cc068074daf2e0f79fbbaba9a66cfff1172b328d81958c734322', 33978),
    SourceReceipt('grid/storage.py', 'cba2176f603ebe303100014e46b0eca83bd121a00af8b1f837498ff9c5ac560b', 10459),
    SourceReceipt('grid/segment_wal.py', 'eebe62044131912c9cf2dbd4cdb1dd07599e03988ba7a3868b887313f807ef79', 10167),
    SourceReceipt('grid/control_state.py', '6029b701ad89124773af32dc9b51bf3d83653aa92b7f0a1a9c8c4f7ef97a04ba', 2756),
    SourceReceipt('grid/level_generator.py', 'ec0300fa7a17c9389fead873648117db7683d271c5d086d1fac403d8bd3f0cd8', 2666),
    SourceReceipt('grid/legacy_working_copy.py', '1e3c6db9582c46dac0baf3623fe0aa9d48d0a1ac8c851d0aa12b1738db3d2dd1', 576),
    SourceReceipt('grid/config.py', '2e590b2cfdd9162df78bef3aceda01c37b8502e5f7a0bb83160fc5eb22faf3bc', 2819),
)
_MISSING = (
    'first_availability_history', 'retained_revisions',
    'cross_source_coherence', 'market_partition_authority',
    'physical_schema_identity', 'source_completeness_receipts',
    'producer_issued_immutable_export',
)


def pinned_grid_readiness() -> GridReadiness:
    """Describe this pinned audit, without asserting any current source access."""
    return GridReadiness(GRID_SOURCE_COMMIT, _RECEIPTS, _MISSING)


def verify_pinned_grid_source(source_commit: str,
                              source_files: Mapping[str, bytes]) -> GridReadiness:
    """Confirm exact inspected blobs; perform no filesystem, DB, or network IO."""
    if source_commit != GRID_SOURCE_COMMIT:
        raise ValueError('unreviewed Grid source commit')
    if not isinstance(source_files, Mapping) or set(source_files) != {r.path for r in _RECEIPTS}:
        raise ValueError('Grid source membership mismatch')
    for receipt in _RECEIPTS:
        data = source_files[receipt.path]
        if type(data) is not bytes:
            raise ValueError('Grid source bytes required')
        if len(data) != receipt.byte_count or hashlib.sha256(data).hexdigest() != receipt.sha256:
            raise ValueError('Grid source digest mismatch: ' + receipt.path)
    return pinned_grid_readiness()


class NativeGridExportBlocked(RuntimeError):
    """Actual pinned Grid lacks facts required to issue a usable historical cut."""


def require_native_grid_export() -> None:
    """Fail closed before any physical IO; caller claims cannot override missing facts."""
    raise NativeGridExportBlocked('native Grid export BLOCKED: ' + ', '.join(_MISSING))
