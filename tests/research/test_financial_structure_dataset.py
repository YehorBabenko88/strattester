import pytest
from strattester.research.financial_structure_dataset import make_samples


def test_labels_do_not_enter_features():
    ts = [i * 60000 for i in range(35)]
    prices = [100 + i for i in range(35)]
    samples = make_samples("SOLUSDT", "1m", ts, prices, window=4, horizon=3)
    changed = prices[:]
    changed[-1] = 10000
    other = make_samples("SOLUSDT", "1m", ts, changed, window=4, horizon=3)
    assert samples[0].representation == other[0].representation
    assert samples[0].origin_timestamp < samples[0].target_timestamp
    assert samples[-1].target_timestamp == ts[-1]


def test_invalid_horizon():
    with pytest.raises(ValueError):
        make_samples("BTCUSDT", "1m", list(range(20)),
                     [100] * 20, window=4, horizon=1)
