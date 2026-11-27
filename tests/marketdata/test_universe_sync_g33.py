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
