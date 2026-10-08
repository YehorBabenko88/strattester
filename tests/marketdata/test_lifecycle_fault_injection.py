import pytest

from strattester.marketdata.instruments import (
    InstrumentRegistry,
    InstrumentStatus,
)
from strattester.marketdata.errors import DatasetUnavailableError
from strattester.marketdata.universe_sync import (
    UniverseSynchronizer,
    UniverseSnapshotError,
)
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import (
    SyncEngine,
    DataRequirement,
    SyncState,
)


class UniverseClient:
    def __init__(self, symbols):
        self.symbols = set(symbols)
        self.error = None

    def fetch_linear_symbols(self):
        if self.error is not None:
            raise self.error
        return set(self.symbols)


def test_catastrophic_partial_snapshot_is_rejected_without_registry_mutation(tmp_path):
    symbols = {f"S{i:03d}USDT" for i in range(100)}

    reg = InstrumentRegistry.open(tmp_path / "registry.db")
    client = UniverseClient(symbols)
    sync = UniverseSynchronizer(reg, client)

    sync.sync(1000)

    # Simulate a broken/premature exchange response containing only 40%
    # of the previously active universe.
    client.symbols = set(sorted(symbols)[:40])

    with pytest.raises(UniverseSnapshotError, match="shrank suspiciously"):
        sync.sync(2000)

    assert reg.active_symbols() == symbols
    assert all(reg.get(s).status is InstrumentStatus.ACTIVE for s in symbols)
    assert all(reg.intervals(s) == [(1000, None)] for s in symbols)

    # A later healthy snapshot must still reconcile normally.
    client.symbols = symbols | {"NEWUSDT"}
    sync.sync(3000)

    assert reg.get("NEWUSDT").status is InstrumentStatus.ACTIVE
    assert reg.intervals("NEWUSDT") == [(3000, None)]

    reg.close()


def test_exact_old_shrink_threshold_is_rejected_as_mass_disappearance(tmp_path):
    """
    ratio == minimum_snapshot_ratio is not sufficient evidence when the
    absolute disappearance is also large.

    100 -> 50 must therefore be rejected before lifecycle mutation.
    """
    symbols = {f"S{i:03d}USDT" for i in range(100)}

    reg = InstrumentRegistry.open(tmp_path / "registry.db")
    client = UniverseClient(symbols)
    sync = UniverseSynchronizer(
        reg,
        client,
        minimum_snapshot_ratio=0.5,
    )

    sync.sync(1000)

    survivors = set(sorted(symbols)[:50])
    client.symbols = survivors

    with pytest.raises(
        UniverseSnapshotError,
        match="lost too many previously active symbols",
    ):
        sync.sync(2000)

    assert reg.active_symbols() == symbols

    with pytest.raises(
        UniverseSnapshotError,
        match="lost too many previously active symbols",
    ):
        sync.sync(3000)

    assert reg.active_symbols() == symbols

    reg.close()

def test_universe_api_exception_cannot_mutate_registry(tmp_path):
    symbols = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    reg = InstrumentRegistry.open(tmp_path / "registry.db")
    client = UniverseClient(symbols)
    sync = UniverseSynchronizer(reg, client)

    sync.sync(1000)

    before = {
        s: (reg.get(s), reg.intervals(s))
        for s in symbols
    }

    client.error = ConnectionError("simulated exchange outage")

    with pytest.raises(ConnectionError, match="exchange outage"):
        sync.sync(2000)

    after = {
        s: (reg.get(s), reg.intervals(s))
        for s in symbols
    }

    assert after == before
    reg.close()


def test_rejected_shrink_does_not_consume_missing_confirmation(tmp_path):
    symbols = {f"S{i:03d}USDT" for i in range(100)}

    reg = InstrumentRegistry.open(tmp_path / "registry.db")
    client = UniverseClient(symbols)
    sync = UniverseSynchronizer(reg, client)

    sync.sync(1000)

    victim = "S099USDT"

    # Broken 40% snapshot must not count as the victim's first disappearance.
    client.symbols = set(sorted(symbols)[:40])

    with pytest.raises(UniverseSnapshotError):
        sync.sync(2000)

    assert reg.get(victim).status is InstrumentStatus.ACTIVE
    assert reg.intervals(victim) == [(1000, None)]

    # First VALID snapshot without victim => MISSING, not DELISTED.
    client.symbols = symbols - {victim}
    sync.sync(3000)

    assert reg.get(victim).status is InstrumentStatus.MISSING
    assert reg.intervals(victim) == [(1000, 3000)]

    # Second valid observation confirms it.
    sync.sync(4000)

    assert reg.get(victim).status is InstrumentStatus.DELISTED
    assert reg.get(victim).delisted_at == 4000

    reg.close()


def test_dataset_exception_does_not_poison_other_dataset(tmp_path):
    class Client:
        def fetch_klines(self, *args):
            return [["0", "1", "1", "1", "1", "1", "1"]]

        def fetch_open_interest(self, *args):
            raise DatasetUnavailableError(
                "not available for this symbol"
            )

    store = SQLiteMarketStore.open(tmp_path / "market.db")
    engine = SyncEngine(store, Client(), clock_ms=lambda: 999999)

    unavailable = engine.sync_requirement(
        DataRequirement("XUSDT", "open_interest", "5m", 0, 0)
    )

    candles = engine.sync_requirement(
        DataRequirement("XUSDT", "candles", "1m", 0, 0)
    )

    assert unavailable.state is SyncState.UNAVAILABLE
    assert candles.state is SyncState.READY
    assert store.coverage("XUSDT", "candles", "1m").count == 1

    store.close()


def test_unknown_dataset_failure_is_not_misreported_ready(tmp_path):
    class Client:
        pass

    store = SQLiteMarketStore.open(tmp_path / "market.db")
    engine = SyncEngine(store, Client(), clock_ms=lambda: 999999)

    result = engine.sync_requirement(
        DataRequirement("XUSDT", "future_unknown_dataset", "1m", 0, 0)
    )

    assert result.state is SyncState.REPAIR_REQUIRED
    assert "unsupported" in result.message.lower()

    store.close()


def test_repeated_large_partial_snapshot_must_not_mass_delist_universe(tmp_path):
    """
    A large non-empty universe shrink must be rejected before reconcile().

    700 -> 400 is still large enough to pass the historical 50% minimum-size
    guard, but disappearance of 300 active instruments at once is not safe
    delisting evidence.

    Rejected snapshots must not consume missing confirmations or alter
    lifecycle intervals.
    """
    symbols = {f"S{i:03d}USDT" for i in range(700)}

    reg = InstrumentRegistry.open(tmp_path / "registry.db")
    client = UniverseClient(symbols)

    sync = UniverseSynchronizer(
        reg,
        client,
        minimum_snapshot_ratio=0.5,
    )

    sync.sync(1000)

    assert len(reg.active_symbols()) == 700

    survivors = set(sorted(symbols)[:400])
    missing = symbols - survivors

    assert len(survivors) == 400
    assert len(missing) == 300

    client.symbols = survivors

    # First suspicious snapshot must be rejected before registry mutation.
    with pytest.raises(
        UniverseSnapshotError,
        match="lost too many previously active symbols",
    ):
        sync.sync(2000)

    assert reg.active_symbols() == symbols

    for symbol in missing:
        record = reg.get(symbol)
        assert record.status is InstrumentStatus.ACTIVE
        assert reg.intervals(symbol) == [(1000, None)]

    # Repetition of the same bad snapshot still must not turn it into
    # delisting evidence.
    with pytest.raises(
        UniverseSnapshotError,
        match="lost too many previously active symbols",
    ):
        sync.sync(3000)

    assert reg.active_symbols() == symbols

    for symbol in missing:
        record = reg.get(symbol)
        assert record.status is InstrumentStatus.ACTIVE
        assert record.delisted_at is None
        assert reg.intervals(symbol) == [(1000, None)]

    # Recovery: a later healthy snapshot must reconcile normally and may
    # discover new instruments.
    healthy = symbols | {"NEWUSDT"}
    client.symbols = healthy

    result = sync.sync(4000)

    assert result == healthy
    assert reg.get("NEWUSDT").status is InstrumentStatus.ACTIVE
    assert reg.intervals("NEWUSDT") == [(4000, None)]

    reg.close()
