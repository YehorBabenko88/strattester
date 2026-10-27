"""Independent Decimal/time references for executed financial paths.

No Grid database or math-repository implementation is imported. These tests
pin adaptation semantics; they do not certify a native producer or real labels.
"""
from dataclasses import replace
from decimal import Decimal, localcontext
import math

import numpy as np
import pytest

from strattester.research.financial_contract import Bar, Instrument, Snapshot, timestamp_ns
from strattester.research.financial_pipeline import feature_tracks
from strattester.research.financial_structure_dataset import make_samples
from strattester.research.financial_structural_model import StructuralConfig
from strattester.research.financial_experiment import Example, run_experiment


def market(prices, unit=60_000_000_000):
    identity = Instrument('fixture', 'spot', 'USD')
    rows = tuple(Bar(identity, unit, i*unit, (i+1)*unit, (i+1)*unit-1,
                     (i+1)*unit, (i+1)*unit, (i+1)*unit, p,
                     'VERIFIED', True, True, 1, 'fixture', 'a'*40)
                 for i, p in enumerate(prices))
    return Snapshot(rows, len(rows)*unit, 'synthetic', ('fixture',))


@pytest.mark.parametrize('unit,factor', [('ns', 1), ('us', 1000), ('ms', 10**6), ('s', 10**9)])
def test_timestamp_units_remain_exact_above_binary64_integer_range(unit, factor):
    value = 2**53 + 37
    assert timestamp_ns(value, unit) == value * factor
    for bad in (float(value), True, -1):
        with pytest.raises(ValueError):
            timestamp_ns(bad, unit)


@pytest.mark.parametrize('price_scale', [1e-200, 1., 1e200])
def test_actual_features_pin_population_volatility_and_decimal_log_returns(price_scale):
    prices = [price_scale * p for p in [1., 2., 1., 4., 3., 2., 1., 1., 2., 3.]]
    x, mask, _ = feature_tracks(market(prices), timeframe_ns=60_000_000_000, config=StructuralConfig())
    with localcontext() as ctx:
        ctx.prec = 80
        values = [Decimal.from_float(p) for p in prices]
        returns = [Decimal(0)] + [(b/a).ln() for a, b in zip(values, values[1:])]
        expected = []
        for i, r in enumerate(returns):
            window = returns[max(0, i-7):i+1]
            mean = sum(window)/len(window)
            squares = sum((v-mean)**2 for v in window)
            population = (squares/len(window)).sqrt()
            expected.append([float(r), float(mean), float(population)])
        # A sample estimator substitution is an intentional model semantic change.
        assert float((sum((v-sum(returns[:2])/2)**2 for v in returns[:2])).sqrt()) != expected[1][2]
    np.testing.assert_allclose(x[0, 0].numpy(), expected, rtol=2e-6, atol=2e-12)
    assert mask.all()


@pytest.mark.parametrize('horizon', [2, 3, 5])
def test_supervised_targets_match_decimal_bar_count_horizon_and_future_isolation(horizon):
    prices = [100., 102., 99., 104., 98., 110., 105., 103., 112., 108., 115., 109.]
    times = [1_700_000_000_000 + 60_000*i for i in range(len(prices))]
    samples = make_samples('USD', '1m', times, prices, window=3, horizon=horizon)
    first = samples[0]
    assert first.origin_timestamp == times[3]
    assert first.target_timestamp-first.origin_timestamp == horizon*60_000
    with localcontext() as ctx:
        ctx.prec = 80
        p = list(map(Decimal.from_float, prices))
        future = [(p[j]/p[j-1]).ln() for j in range(4, 4+horizon)]
        mean = sum(future)/horizon
        vol = (sum((r-mean)**2 for r in future)/horizon).sqrt()
        expected_return = (p[3+horizon]/p[3]).ln()
        expected_log_vol = vol.ln()
    assert first.future_log_return == pytest.approx(float(expected_return), abs=2e-14)
    assert first.future_log_volatility == pytest.approx(float(expected_log_vol), abs=2e-13)
    changed = prices[:4] + [v*1.5 for v in prices[4:]]
    altered = make_samples('USD', '1m', times, changed, window=3, horizon=horizon)[0]
    assert altered.representation == first.representation
    assert altered.future_log_return != first.future_log_return
    assert math.expm1(first.future_log_return) == pytest.approx(prices[3+horizon]/prices[3]-1, abs=2e-14)


@pytest.mark.parametrize('field,value', [('available_ns', 180_000_000_001),
                                       ('watermark_ns', 179_999_999_999),
                                       ('event_ns', 180_000_000_000),
                                       ('candle_open_ns', 120_000_000_001)])
def test_availability_watermark_and_half_open_event_boundaries_fail_closed(field, value):
    snap = market([100., 101., 102.])
    snap.validate()  # availability == origin and watermark == close are admitted.
    bad = replace(snap.bars[-1], **{field: value})
    with pytest.raises(ValueError):
        replace(snap, bars=(*snap.bars[:-1], bad)).validate()


@pytest.mark.parametrize('delta', [-1, 1, 60_000_000_000])
def test_experiment_rejects_wrong_label_horizon_before_model_allocation(tmp_path, monkeypatch, delta):
    snap = market([100., 101., 102.])
    horizon = 120_000_000_000
    config = StructuralConfig(horizon_ns=horizon)
    example = Example(snap, snap.bars[0].instrument, 60_000_000_000,
                      snap.origin_ns+horizon+delta, .1)
    def forbidden(*args, **kwargs):
        pytest.fail('invalid horizon reached feature/model allocation')
    monkeypatch.setattr('strattester.research.financial_experiment.feature_tracks', forbidden)
    monkeypatch.setattr('strattester.research.financial_experiment.build_structural_model', forbidden)
    with pytest.raises(ValueError, match='label horizon'):
        run_experiment([example], tmp_path/'never-created.json', train_end=1, validation_end=2,
                       test_end=3, config=config, steps=1)
    assert not (tmp_path/'never-created.json').exists()
