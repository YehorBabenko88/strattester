"""Data retains byte/source admission; Math owns historical numeric integrity."""
from copy import deepcopy
from market_data.provenance import data_integrity


def row():
    return dict(open=1, high=2, low=1, close=2, buy_volume=0.3, sell_volume=0.1,
        delta=0.2, trade_count=2, poc_price=2,
        levels=[dict(price=2, buy_volume=0.3, sell_volume=0.1, delta=0.2,
                     volume=0.4, buy_count=1, sell_count=1)])


def test_data_rejects_numeric_partition_refused_by_canonical_math():
    good = row()
    original = deepcopy(good)
    assert data_integrity(good)
    bad = deepcopy(good)
    bad['buy_volume'] = 99
    assert not data_integrity(bad)
    assert good == original


def test_data_byte_budget_remains_independent_of_numeric_integrity():
    original = row()
    assert data_integrity(original)
    oversized = dict(original, evidence='x' * 1048576)
    assert not data_integrity(oversized)
