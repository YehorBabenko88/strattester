import pytest
from strattester.research.alphafold_adapter import encode_market, predict_with_backend


def test_any_instrument_and_alignment():
    features = encode_market("SOLUSDT", "5m", [i * 300000 for i in range(40)],
                             [100 + i for i in range(40)], window=4, max_tokens=7)
    assert len(features.single) == 7
    assert len(features.pair) == 7
    assert features.timestamps[-1] == 39 * 300000
    assert len(features.source_sha256) == 64


def test_future_invariance():
    ts = list(range(40))
    prices = [100 + i for i in ts]
    a = encode_market("ETHUSDT", "1m", ts, prices, window=4)
    b = encode_market("ETHUSDT", "1m", ts + [40], prices + [900], window=4)
    assert b.single[:len(a.single)] == a.single


def test_backend_required():
    f = encode_market("BTCUSDT", "1m", list(range(20)),
                      [100 + i for i in range(20)], window=4)
    with pytest.raises(RuntimeError):
        predict_with_backend(f, None)


def test_injected_backend():
    f = encode_market("XRPUSDT", "1m", list(range(20)),
                      [100 + i for i in range(20)], window=4)
    class Stub:
        def predict(self, features):
            return {"tokens": len(features.single)}
    assert predict_with_backend(f, Stub()) == {"tokens": 16}
