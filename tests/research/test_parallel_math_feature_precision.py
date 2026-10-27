"""Decimal oracles for the actual feature path; no performance inference."""
from decimal import Decimal, localcontext
import math
from types import SimpleNamespace

import pytest
import torch

from strattester.research.financial_contract import Bar, Instrument, Snapshot
from strattester.research.financial_pipeline import feature_tracks, predict_snapshot
from strattester.research.financial_structural_model import StructuralConfig


def snapshot(prices):
    instrument = Instrument('fixture', 'spot', 'USD')
    bars = tuple(Bar(instrument, 60, i*60, (i+1)*60, (i+1)*60-1,
                     (i+1)*60, (i+1)*60, (i+1)*60, p,
                     'VERIFIED', True, True, 1, 'fixture', 'a'*40)
                 for i, p in enumerate(prices))
    return Snapshot(bars, len(bars)*60, 'fixture', ('fixture',))


def oracle(prices):
    # Exact binary inputs, independently evaluated with 100-digit arithmetic.
    with localcontext() as context:
        context.prec = 100
        values = [Decimal.from_float(p) for p in prices]
        returns = [Decimal(0), *((b/a).ln() for a, b in zip(values, values[1:]))]
        expected = []
        for i, value in enumerate(returns):
            window = returns[max(0, i-7):i+1]
            mean = sum(window)/len(window)
            std = (sum((v-mean)**2 for v in window)/len(window)).sqrt()
            expected.append([float(value), float(mean), float(std)])
        return torch.tensor(expected, dtype=torch.float64)


@pytest.mark.parametrize('base', [1e-200, 1., 1e200])
@pytest.mark.parametrize('direction', [0., math.inf])
def test_representable_small_returns_survive_feature_extraction(base, direction):
    prices = [base, math.nextafter(base, direction), base]
    actual = feature_tracks(snapshot(prices), timeframe_ns=60, config=StructuralConfig())[0][0, 0]
    torch.testing.assert_close(actual.double(), oracle(prices), rtol=1e-6, atol=1e-30)
    assert actual[1, 0] != 0


@pytest.mark.parametrize('prices', [
    [1e-300, 1e300, 1e-300],
    [1e300, 1e-300, 1e300],
    [100., 101., 99., 102., 98., 110., 90., 120., 80., 100.],
    [1., 1., 1.],
])
def test_extreme_ratios_and_rolling_moments_match_decimal(prices):
    actual = feature_tracks(snapshot(prices), timeframe_ns=60, config=StructuralConfig())[0][0, 0]
    torch.testing.assert_close(actual.double(), oracle(prices), rtol=1e-6, atol=1e-12)


@pytest.mark.parametrize('timeframe', [0, -60, True, 60.])
def test_predict_validates_timeframe_before_checkpoint_access(timeframe):
    with pytest.raises(ValueError, match='timeframe'):
        predict_snapshot(None, SimpleNamespace(config=StructuralConfig()),
                         instrument=None, timeframe_ns=timeframe, horizon_ns=120,
                         model_sha256='a'*64, available_ns=0)


def test_verified_prediction_consumes_decimal_checked_features(tmp_path):
    from strattester.research.financial_checkpoint import save_checkpoint, load_checkpoint
    from strattester.research.financial_structural_model import build_structural_model
    prices = [1e200, math.nextafter(1e200, math.inf), 1e200]
    data = snapshot(prices)
    model = build_structural_model(StructuralConfig(recycles=2), seed=41)
    path = tmp_path/'checkpoint.json'
    sha = save_checkpoint(model, path, dataset_sha256='b'*64, seed=41)
    loaded, _ = load_checkpoint(path, sha)
    observed = []
    handle = loaded.input.register_forward_pre_hook(lambda module, args: observed.append(args[0].clone()))
    try:
        prediction = predict_snapshot(data, loaded, instrument=data.bars[0].instrument,
                                      timeframe_ns=60, horizon_ns=120, model_sha256=sha,
                                      available_ns=data.origin_ns)
    finally:
        handle.remove()
    assert len(observed) == 1
    torch.testing.assert_close(observed[0][0, 0].double(), oracle(prices), rtol=1e-6, atol=1e-30)
    assert math.isfinite(prediction.mu) and prediction.scale > 0
    assert prediction.horizon_ns == 120


@pytest.mark.parametrize('suffix', [1e-300, 1e300])
def test_available_prefix_features_do_not_use_later_prices(suffix):
    prefix = [1e200, math.nextafter(1e200, math.inf), 1e200]
    before = feature_tracks(snapshot(prefix), timeframe_ns=60, config=StructuralConfig())[0]
    after = feature_tracks(snapshot([*prefix, suffix]), timeframe_ns=60, config=StructuralConfig())[0]
    torch.testing.assert_close(before, after[:, :, :len(prefix)], rtol=0, atol=0)
