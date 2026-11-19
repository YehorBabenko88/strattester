"""Legacy universe reconciliation from an independently qualified Grid snapshot.

Never fetch symbols directly from Bybit in this transitional Strattester path.
A partial/unattested snapshot must never delist or mutate persisted identity.
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
            raise UniverseSnapshotError("GRID_SNAPSHOT_REQUIRED: direct client forbidden")

    def sync(self, observed_at: int, *, snapshot=None):
        # Snapshot must be provided by the owner after independent source
        # qualification. There is deliberately no fallback REST/WS client.
        if type(snapshot) is not dict:
            raise UniverseSnapshotError("GRID_SNAPSHOT_REQUIRED")
        if snapshot.get("api_version") != "grid.instrument.snapshot.v1":
            raise UniverseSnapshotError("GRID_SNAPSHOT_VERSION_REQUIRED")
        if snapshot.get("source_qualified") is not True:
            raise UniverseSnapshotError("GRID_SNAPSHOT_NOT_QUALIFIED")
        if snapshot.get("complete") is not True:
            raise UniverseSnapshotError("GRID_UNIVERSE_INCOMPLETE")
        if type(observed_at) is not int or observed_at < 0:
            raise UniverseSnapshotError("INVALID_OBSERVATION_TIME")
        if snapshot.get("observed_at_ms") != observed_at:
            raise UniverseSnapshotError("GRID_SNAPSHOT_TIME_MISMATCH")
        raw = snapshot.get("symbols")
        if type(raw) not in (tuple, list) or any(
            type(symbol) is not str or not symbol.strip() for symbol in raw
        ):
            raise UniverseSnapshotError("GRID_SNAPSHOT_SYMBOLS_INVALID")
        symbols = set(raw)
        active = set(self.registry.active_symbols())
        if active:
            if not symbols:
                raise UniverseSnapshotError(
                    "empty complete snapshot would mass delist instruments"
                )
            if len(symbols) / len(active) < self.minimum_snapshot_ratio:
                raise UniverseSnapshotError("suspicious Grid universe contraction")
        self.registry.reconcile(symbols, observed_at)
        return symbols
