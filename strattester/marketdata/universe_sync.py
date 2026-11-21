"""Legacy Strattester universe synchronizer is disabled pending Grid attestation.

Grid's current instrument-state/backfill-state v1 endpoints are INFORMATIONAL
and source_provenance/history_coverage are NOT_ATTESTED. A plain caller-supplied
dict, even one claiming source_qualified=True, cannot prove an authenticated,
complete market universe. Never mutate the old registry from that assertion.
"""
class UniverseSnapshotError(RuntimeError):
    pass


class UniverseSynchronizer:
    def __init__(self, registry, client=None, minimum_snapshot_ratio: float = 0.5):
        self.registry = registry
        self.minimum_snapshot_ratio = float(minimum_snapshot_ratio)
        if not 0 < self.minimum_snapshot_ratio <= 1:
            raise ValueError("invalid minimum_snapshot_ratio")
        if client is not None:
            raise UniverseSnapshotError("DIRECT_EXCHANGE_CLIENT_FORBIDDEN")

    def sync(self, observed_at: int, *, snapshot=None):
        # No verified, authenticated full-universe Grid API is admitted yet.
        # Do not trust arbitrary booleans/provenance labels in an input dict.
        # This compatibility entrypoint cannot fetch Bybit or write SQL.
        raise UniverseSnapshotError("GRID_VERIFIED_UNIVERSE_API_UNAVAILABLE")
