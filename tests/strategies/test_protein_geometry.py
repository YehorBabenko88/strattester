from types import SimpleNamespace
from strattester.strategies.builtin.protein_geometry import ProteinGeometryResearch, protein_geometry_definition
from strattester.research.protein_geometry_offline import run_universe_offline


def test_disabled_by_default():
    assert protein_geometry_definition().enabled is False


def test_generic_symbol_features_only():
    rows = [SimpleNamespace(open_time=i * 60000, close=100 + i) for i in range(25)]
    context = SimpleNamespace(symbol="ETHUSDT", candles=lambda tf: iter(rows))
    output = ProteinGeometryResearch().run_context(context)
    assert output["symbol"] == "ETHUSDT"
    assert output["status"] == "FEATURES_ONLY"
    assert len(output["points"]) == 9
    assert output["trades"] == []


def test_universe_failure_isolation():
    class Store:
        def coverage(self, symbol, dataset, timeframe, **kwargs):
            return SimpleNamespace(count=0, gaps=())
    result = run_universe_offline(Store(), ["BTCUSDT", "ETHUSDT"])
    assert set(result) == {"BTCUSDT", "ETHUSDT"}
    assert all(v["status"] == "BLOCKED" for v in result.values())
