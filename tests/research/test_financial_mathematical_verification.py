"""Independent Decimal/NumPy checks of executed financial boundaries.

These are finite-domain properties, not upstream math-repository parity.
CPU dependencies are mandatory: a missing dependency must fail collection.
"""
from dataclasses import replace
from decimal import Decimal, localcontext
import math
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from research.independent_decimal_oracles import decimal_gaussian_nll, decimal_returns
from research.independent_time_oracles import ms_to_ns, ns_to_ms_exact
from strattester.research.financial_contract import Bar, Instrument, Snapshot, Prediction, timestamp_ns
from strattester.research.financial_pipeline import feature_tracks
from strattester.research.financial_structural_model import StructuralConfig
from strattester.research.financial_evaluation import gaussian_scores, evaluate_ledger, Trade
from strattester.research.alphafold_outer_product import build_outer_product_mean
from research.math_contract_reference import train_only_zscore


@pytest.mark.parametrize('milliseconds', [0, 1, 999, 1_729_123_456_789, 2**53+1, 2**63-1])
def test_integer_time_conversion_has_no_float_roundtrip(milliseconds):
    ns = timestamp_ns(milliseconds, 'ms')
    assert ns == ms_to_ns(milliseconds)
    assert ns_to_ms_exact(ns) == milliseconds
    assert timestamp_ns(ns, 'ns') == ns
    with pytest.raises(ValueError):
        ns_to_ms_exact(ns+1)


def snapshot(prices):
    instrument = Instrument('test', 'spot', 'USD')
    rows = tuple(Bar(instrument, 60, i*60, (i+1)*60, (i+1)*60-1,
                     (i+1)*60, (i+1)*60, (i+1)*60, float(p),
                     'VERIFIED', True, True, 1, 'fixture', 'a'*40)
                 for i, p in enumerate(prices))
    return Snapshot(rows, len(rows)*60, 'fixture', ('fixture',))


@pytest.mark.parametrize('prices', [
    [100., 101., 99., 102., 98., 110., 90., 120., 80., 100.],
    [1e-200, 2e-200, 1e-200, 4e-200],
    [1e200, 2e200, 1e200, 4e200],
    [1., 1., 1., 1.],
])
def test_actual_feature_channels_match_decimal_population_moments(prices):
    features, mask, _ = feature_tracks(snapshot(prices), timeframe_ns=60, config=StructuralConfig())
    returns = [Decimal(0), *(row[0] for row in decimal_returns(prices))]
    expected = []
    with localcontext() as ctx:
        ctx.prec = 70
        for i, value in enumerate(returns):
            window = returns[max(0, i-7):i+1]
            mean = sum(window)/len(window)
            vol = (sum((r-mean)**2 for r in window)/len(window)).sqrt()
            expected.append([float(value), float(mean), float(vol)])
    # Producer intentionally exports float32; oracle calculations retain 70 digits.
    np.testing.assert_allclose(features[0, 0].numpy(), expected, rtol=2e-6, atol=2e-12)
    assert mask.all()


@pytest.mark.parametrize('power', [-150, -10, 0, 10, 150])
def test_price_numeraire_invariance_and_simple_log_distinction(power):
    prices = [1., 2., 1., 4.]
    a = feature_tracks(snapshot(prices), timeframe_ns=60, config=StructuralConfig())[0]
    b = feature_tracks(snapshot([p*10.**power for p in prices]), timeframe_ns=60, config=StructuralConfig())[0]
    torch.testing.assert_close(a, b, rtol=1e-6, atol=1e-12)
    log_return, simple_return = decimal_returns(prices)[0]
    result = evaluate_ledger([Trade('USD', 0, 60, float(simple_return), 1)])
    assert result['returns'] == [1.]
    assert not math.isclose(float(log_return), result['returns'][0])


@pytest.mark.parametrize('mu,scale,target', [(0.,1.,0.), (.03,.2,-.1), (1e4,1e-5,1e4+1e-5), (-10.,10.,20.)])
def test_actual_gaussian_score_matches_decimal_and_change_of_units(mu, scale, target):
    actual = gaussian_scores([mu], [scale], [target])
    # Decimal(str(float)) describes decimal input, allowing binary cancellation at large offsets.
    expected = float(decimal_gaussian_nll(mu, scale, target))
    assert actual['nll'] == pytest.approx(expected, rel=1e-7, abs=1e-7)
    translated = gaussian_scores([mu+3], [scale], [target+3])
    assert translated['nll'] == pytest.approx(actual['nll'], rel=1e-7, abs=1e-7)
    scaled = gaussian_scores([mu*2], [scale*2], [target*2])
    assert scaled['nll'] == pytest.approx(actual['nll']+math.log(2), rel=1e-12)
    assert scaled['coverage_95'] == actual['coverage_95']


@pytest.mark.parametrize('seed', [0, 7, 29])
def test_actual_pair_normalization_matches_scalar_numpy_oracle(seed):
    torch.manual_seed(seed)
    op = build_outer_product_mean(3, 2, 2).double()
    x = np.random.default_rng(seed).normal(size=(1, 3, 4, 3))
    mask = np.array([[[1,1,0,0], [1,0,1,0], [0,1,1,0]]], dtype=bool)
    state = {k: v.detach().numpy() for k,v in op.state_dict().items()}
    expected = np.zeros((1,4,4,2))
    normalized = (x-x.mean(-1,keepdims=True))/np.sqrt(x.var(-1,keepdims=True)+op.norm.eps)
    normalized = normalized*state['norm.weight']+state['norm.bias']
    left = normalized@state['left.weight'].T+state['left.bias']
    right = normalized@state['right.weight'].T+state['right.bias']
    for i in range(4):
        for j in range(4):
            valid = [s for s in range(3) if mask[0,s,i] and mask[0,s,j]]
            if valid:
                terms = [np.outer(left[0,s,i], right[0,s,j]) for s in valid]
                expected[0,i,j] = (sum(terms)/len(valid)).reshape(-1)@state['output.weight'].T+state['output.bias']
    actual = op(torch.from_numpy(x), torch.from_numpy(mask)).detach().numpy()
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=2e-12)
    # Repeating the set of aligned tracks changes neither the mean nor denominator.
    duplicated = op(torch.from_numpy(np.repeat(x,2,axis=1)), torch.from_numpy(np.repeat(mask,2,axis=1)))
    np.testing.assert_allclose(duplicated.detach().numpy(), expected, rtol=2e-12, atol=2e-12)


@pytest.mark.parametrize('horizon', [1, 60, 120, 2**63+1])
def test_prediction_preserves_integer_horizon_without_unit_inference(horizon):
    p = Prediction(Instrument('test','spot','USD'), 60, 60, horizon, .1, .2, 'a'*64, 'b'*64)
    p.validate()
    assert p.horizon_ns == horizon
    for invalid in [0, -1, True, 120.]:
        with pytest.raises(ValueError):
            replace(p, horizon_ns=invalid).validate()


@pytest.mark.parametrize('horizon,timeframe', [(60,60), (121,60), (120,70), (120_000_000,60)])
def test_inference_rejects_untrained_or_misaligned_horizon_before_model_access(horizon,timeframe):
    from strattester.research.financial_pipeline import predict_snapshot
    with pytest.raises(ValueError, match='horizon'):
        predict_snapshot(None, SimpleNamespace(config=StructuralConfig(horizon_ns=120)),
                         instrument=None, timeframe_ns=timeframe, horizon_ns=horizon,
                         model_sha256='a'*64, available_ns=0)


@pytest.mark.parametrize('seed', [1, 11, 31])
def test_reference_only_train_normalization_matches_decimal_and_ignores_test_fit(seed):
    # This helper is a reference contract, NOT a scaler used by feature_tracks.
    rng = np.random.default_rng(seed)
    train = rng.normal(size=17).tolist()
    query = [-1., 0., 1.]
    actual, state = train_only_zscore(train, query)
    with localcontext() as ctx:
        ctx.prec = 70
        values = [Decimal(str(v)) for v in train]
        mean = sum(values)/len(values)
        std = (sum((v-mean)**2 for v in values)/len(values)).sqrt()
        expected = [float((Decimal(str(v))-mean)/std) for v in query]
    np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=2e-14)
    extended, extended_state = train_only_zscore(train, [*query, 1e100])
    assert state == extended_state
    assert extended[:3] == actual
