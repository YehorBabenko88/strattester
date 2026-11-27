import pytest

from strattester.marketdata.instruments import InstrumentRegistry, InstrumentStatus
from strattester.marketdata.universe_sync import UniverseSnapshotError, UniverseSynchronizer


class MutableSource:
    def __init__(self, symbols):
        self.symbols = symbols

    def fetch_linear_symbols(self):
        return self.symbols


@pytest.mark.parametrize("bad", [
    "BTCUSDT", {"BTCUSDT": True}, None, 0,
    ["BTCUSDT", "BTCUSDT"], ["BTCUSDT", " btcusdt"],
    ["BTCUSDT", "BTC USDT"], ["BTCUSDT", False],
    ["BTCUSDT", "ETHUSD"], ["BTCUSDT", "BTCUSDT\\n"],
])
def test_untrusted_grid_universe_snapshot_cannot_mass_delist(tmp_path, bad):
    registry = InstrumentRegistry.open(tmp_path / "instruments.sqlite3")
    source = MutableSource({"BTCUSDT", "ETHUSDT"})
    sync = UniverseSynchronizer(registry, source)
    assert sync.sync(1000) == {"BTCUSDT", "ETHUSDT"}
    before = registry.conn.execute(
        "SELECT symbol,status,last_seen,missing_count FROM instruments ORDER BY symbol"
    ).fetchall()
    source.symbols = bad
    with pytest.raises(UniverseSnapshotError):
        sync.sync(2000)
    after = registry.conn.execute(
        "SELECT symbol,status,last_seen,missing_count FROM instruments ORDER BY symbol"
    ).fetchall()
    assert after == before
    assert registry.active_symbols() == {"BTCUSDT", "ETHUSDT"}
    assert all(registry.get(s).status is InstrumentStatus.ACTIVE for s in before_symbol_names())
    registry.close()


def before_symbol_names():
    return ("BTCUSDT", "ETHUSDT")


@pytest.mark.parametrize("ratio", [0, -1, float("nan"), float("inf"), 1.1])
def test_unsafe_minimum_snapshot_ratio_denied(tmp_path, ratio):
    registry = InstrumentRegistry.open(tmp_path / "instruments.sqlite3")
    with pytest.raises(ValueError):
        UniverseSynchronizer(registry, MutableSource({"BTCUSDT"}), ratio)
    registry.close()


def test_valid_snapshot_preserves_missing_confirmation_protocol(tmp_path):
    registry = InstrumentRegistry.open(tmp_path / "instruments.sqlite3")
    source = MutableSource({"BTCUSDT", "ETHUSDT"})
    sync = UniverseSynchronizer(registry, source)
    assert sync.sync(1000) == {"BTCUSDT", "ETHUSDT"}
    source.symbols = {"BTCUSDT"}
    assert sync.sync(2000) == {"BTCUSDT"}
    assert registry.get("ETHUSDT").status is InstrumentStatus.MISSING
    assert sync.sync(3000) == {"BTCUSDT"}
    assert registry.get("ETHUSDT").status is InstrumentStatus.DELISTED
    registry.close()


def test_g34_disjoint_equal_size_snapshots_never_mutate_original_sqlite(tmp_path):
    path = tmp_path / "instruments.sqlite3"
    registry = InstrumentRegistry.open(path)
    source = MutableSource({"BTCUSDT", "ETHUSDT"})
    sync = UniverseSynchronizer(registry, source)
    assert sync.sync(1000) == {"BTCUSDT", "ETHUSDT"}
    tables = ("instruments", "instrument_intervals", "instrument_registry_meta")
    def snapshot():
        return {table: registry.conn.execute(
            "SELECT * FROM " + table + " ORDER BY 1"
        ).fetchall() for table in tables}
    original = snapshot()
    source.symbols = {"FOOUSDT", "BARUSDT"}
    for timestamp in (2000, 3000, 4000):
        with pytest.raises(UniverseSnapshotError):
            sync.sync(timestamp)
        assert snapshot() == original
        assert registry.active_symbols() == {"BTCUSDT", "ETHUSDT"}
        assert registry.get("BTCUSDT").status is InstrumentStatus.ACTIVE
        assert registry.get("ETHUSDT").status is InstrumentStatus.ACTIVE
    registry.close()
    reopened = InstrumentRegistry.open(path)
    assert reopened.active_symbols() == {"BTCUSDT", "ETHUSDT"}
    assert reopened.get("BTCUSDT").status is InstrumentStatus.ACTIVE
    assert reopened.get("ETHUSDT").status is InstrumentStatus.ACTIVE
    reopened.close()


def test_g34_overlap_count_not_just_total_size(tmp_path):
    registry = InstrumentRegistry.open(tmp_path / "instruments.sqlite3")
    source = MutableSource({"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"})
    sync = UniverseSynchronizer(registry, source)
    assert len(sync.sync(1000)) == 4
    source.symbols = {"BTCUSDT", "FOOUSDT", "BARUSDT", "BAZUSDT"}
    with pytest.raises(UniverseSnapshotError):
        sync.sync(2000)
    assert registry.active_symbols() == {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"}
    registry.close()


@pytest.mark.parametrize("payload", [
    {"status": "INFORMATIONAL", "symbols": ["BTCUSDT"],
     "consumer_cutover_authorized": False, "delisting_authorized": False},
    {"status": "UNAVAILABLE", "symbols": [],
     "consumer_cutover_authorized": False, "delisting_authorized": False},
    {"status": "INFORMATIONAL", "symbols": ["BTCUSDT", "ETHUSDT"],
     "exchange_completeness": "NOT_ATTESTED",
     "consumer_cutover_authorized": False},
    {"status": "INFORMATIONAL", "symbols": ["BTCUSDT"],
     "source_authenticity": "NOT_INDEPENDENTLY_ATTESTED"},
])
def test_g35_observational_roster_cannot_reconcile_registry(tmp_path, payload):
    """Informational Grid roster is not an authority to mutate SQLite."""
    path = tmp_path / "instruments.sqlite3"
    registry = InstrumentRegistry.open(path)
    source = MutableSource({"BTCUSDT", "ETHUSDT"})
    synchronizer = UniverseSynchronizer(registry, source)
    assert synchronizer.sync(1000) == {"BTCUSDT", "ETHUSDT"}
    tables = ("instruments", "instrument_intervals", "instrument_registry_meta")
    before = {table: registry.conn.execute(
        f"SELECT * FROM {table} ORDER BY 1"
    ).fetchall() for table in tables}
    source.symbols = payload
    with pytest.raises(UniverseSnapshotError):
        synchronizer.sync(2000)
    for table in tables:
        assert registry.conn.execute(
            f"SELECT * FROM {table} ORDER BY 1"
        ).fetchall() == before[table]
    registry.close()
    reopened = InstrumentRegistry.open(path)
    assert reopened.active_symbols() == {"BTCUSDT", "ETHUSDT"}
    assert reopened.get("BTCUSDT").status is InstrumentStatus.ACTIVE
    assert reopened.get("ETHUSDT").status is InstrumentStatus.ACTIVE
    reopened.close()
