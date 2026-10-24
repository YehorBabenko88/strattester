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


def test_offline_store_exposes_only_read_capabilities():
    from strattester.research.protein_geometry_offline import _ReadOnlyStore

    class Store:
        def coverage(self, *args, **kwargs):
            return SimpleNamespace(count=0, gaps=())

        def iter_candles(self, *args, **kwargs):
            return iter(())

        def execute_order(self, *args, **kwargs):
            raise AssertionError('order execution must not be exposed')

        def insert_candle(self, *args, **kwargs):
            raise AssertionError('writes must not be exposed')

    view = _ReadOnlyStore(Store())
    assert view.coverage('BTCUSDT', 'candles', '1m').count == 0
    assert list(view.iter_candles('BTCUSDT', '1m')) == []
    assert not hasattr(view, 'execute_order')
    assert not hasattr(view, 'insert_candle')


def test_universe_rejects_string_instead_of_symbols():
    import pytest
    with pytest.raises(ValueError, match='sequence'):
        run_universe_offline(object(), 'BTCUSDT')
