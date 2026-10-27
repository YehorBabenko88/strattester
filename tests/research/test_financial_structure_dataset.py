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


def test_insufficient_history_fails_closed():
    with pytest.raises(ValueError, match='insufficient history'):
        make_samples('BTCUSDT', '1m', list(range(7)), [100.0] * 7, window=4, horizon=3)


def test_future_changes_do_not_modify_past_features():
    ts = [i * 60000 for i in range(40)]
    prices = [100.0 + i for i in range(40)]
    baseline = make_samples('BTCUSDT', '1m', ts, prices, window=4, horizon=3)
    altered = prices[:]
    for i in range(20, 40):
        altered[i] = prices[i] * 1.5
    mutated = make_samples('BTCUSDT', '1m', ts, altered, window=4, horizon=3)
    for a, b in zip(baseline, mutated):
        if a.origin_timestamp < ts[20]:
            assert a.representation == b.representation


def test_last_valid_origin_is_included():
    ts = [i * 60000 for i in range(12)]
    samples = make_samples('BTCUSDT', '1m', ts, [100.0 + i for i in range(12)], window=4, horizon=3)
    assert len(samples) == 12 - 4 - 3
    assert samples[-1].target_timestamp == ts[-1]


def test_excessive_tokens_rejected():
    with pytest.raises(ValueError, match='max_tokens'):
        make_samples('BTCUSDT', '1m', list(range(12)), [100.0] * 12, window=4, horizon=3, max_tokens=1025)
