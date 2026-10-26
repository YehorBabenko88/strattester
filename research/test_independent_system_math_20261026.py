"""Independent high-precision mathematical contract tests; no upstream code copied."""
import math
import random
from decimal import Decimal, localcontext

import pytest

from research.math_contract_reference import log_returns, sample_volatility, validate_observations
from strattester.research.financial_evaluation import Trade, evaluate_ledger, gaussian_scores
from strattester.research.financial_structure_dataset import make_samples


def test_decimal_return_and_telescoping_oracle():
    rng = random.Random(20261026)
    with localcontext() as ctx:
        ctx.prec = 70
        for _ in range(100):
            prices = [Decimal(str(math.exp(rng.uniform(-12, 12)))) for _ in range(12)]
            expected = [(b.ln() - a.ln()) for a, b in zip(prices, prices[1:])]
            observed = log_returns([float(x) for x in prices])
            for a, b in zip(observed, expected):
                assert a == pytest.approx(float(b), abs=1e-12)
            assert math.fsum(observed) == pytest.approx(float(prices[-1].ln()-prices[0].ln()), abs=1e-12)


def test_sample_vs_population_volatility_oracle():
    values = [-.02, .01, .04]
    with localcontext() as ctx:
        ctx.prec = 70
        d = [Decimal(str(x)) for x in values]
        mean = sum(d)/len(d)
        sample = (sum((x-mean)**2 for x in d)/(len(d)-1)).sqrt()
        population = (sum((x-mean)**2 for x in d)/len(d)).sqrt()
        assert sample_volatility(values) == pytest.approx(float(sample), abs=1e-14)
        assert float(sample) > float(population)


def test_gaussian_nll_decimal_oracle():
    with localcontext() as ctx:
        ctx.prec = 70
        pi = Decimal('3.141592653589793238462643383279502884197169399375105820974944')
        for mu, sigma, target in [(0, 1, 0), (.2, .5, -.3), (-2, 3, 1)]:
            m, s, y = [Decimal(str(x)) for x in (mu, sigma, target)]
            expected = s.ln() + ((y-m)/s)**2/2 + (2*pi).ln()/2
            assert gaussian_scores([mu], [sigma], [target])['nll'] == pytest.approx(float(expected), abs=1e-12)


def test_decimal_ledger_oracle_and_overlap():
    rows = [Trade('BTCUSDT', 0, 10, .02, 1), Trade('BTCUSDT', 10, 20, -.03, -1)]
    result = evaluate_ledger(rows, fee_bps=5, slippage_bps=3, funding_bps=2)
    with localcontext() as ctx:
        ctx.prec = 70
        expected = [Decimal('.02')-Decimal('18')/10000, Decimal('.03')-Decimal('18')/10000]
        for actual, value in zip(result['returns'], expected):
            assert actual == pytest.approx(float(value), abs=1e-14)
    with pytest.raises(ValueError):
        evaluate_ledger([rows[0], Trade('BTCUSDT', 9, 20, .01, 1)])


def test_prefix_invariance_and_target_alignment():
    times = [i * 60_000 for i in range(32)]
    prices = [100.0 + i for i in range(32)]
    base = make_samples('BTCUSDT', '1m', times, prices, window=4, horizon=3)
    modified = prices[:]
    modified[-1] = 10000.
    later = make_samples('BTCUSDT', '1m', times, modified, window=4, horizon=3)
    assert base[0].representation == later[0].representation
    assert all(x.target_timestamp - x.origin_timestamp == 3*60_000 for x in base)
    assert base[-1].target_timestamp == times[-1]


def test_pit_negative_future_and_duplicate():
    row = dict(event_id='x',event_time_ns=1,available_time_ns=10,bucket_end_ns=9,
               eligible=True,quality_status='VERIFIED',gap_status='NONE')
    assert validate_observations([row],10,9)
    with pytest.raises(ValueError):
        validate_observations([row],9,9)
    with pytest.raises(ValueError):
        validate_observations([row,row],10,9)


def test_nonfinite_extreme_and_out_of_order_negative_cases():
    for prices in ([100., float('nan'), 101.], [100., float('inf'), 101.], [100., 0., 101.]):
        with pytest.raises(ValueError):
            log_returns(prices)
    for times in ([0, 60_000, 60_000, 180_000, 240_000, 300_000, 360_000, 420_000],
                  [0, 120_000, 60_000, 180_000, 240_000, 300_000, 360_000, 420_000]):
        with pytest.raises(ValueError):
            make_samples('BTCUSDT','1m',times,[100.]*len(times),window=3,horizon=2)


def test_metamorphic_price_scale_invariance():
    rng = random.Random(19)
    for _ in range(100):
        prices = [math.exp(rng.uniform(-8,8)) for _ in range(10)]
        factor = math.exp(rng.uniform(-5,5))
        assert log_returns(prices) == pytest.approx(log_returns([p*factor for p in prices]),abs=1e-12)


def test_gaussian_calibration_coverage_is_not_nll():
    scores = gaussian_scores([0.,0.,0.], [1.,1.,1.], [0.,1.,3.])
    assert scores['coverage_95'] == pytest.approx(2/3)
    assert scores['mae'] == pytest.approx(4/3)
    assert math.isfinite(scores['nll'])


def test_cost_ledger_zero_position_and_extreme_input():
    flat = evaluate_ledger([Trade('BTCUSDT',0,10,.02,0)],
                           fee_bps=100, slippage_bps=100, funding_bps=100)
    assert flat['returns'] == pytest.approx([0.])
    for bad in (float('nan'),float('inf')):
        with pytest.raises(ValueError):
            evaluate_ledger([Trade('BTCUSDT',0,10,bad,1)])


def test_target_last_bar_mutation_only_changes_affected_label():
    times=[i*60_000 for i in range(24)]
    prices=[100.+i for i in range(24)]
    base=make_samples('BTCUSDT','1m',times,prices,window=4,horizon=3)
    altered=prices[:]
    altered[-1]=altered[-1]*2
    new=make_samples('BTCUSDT','1m',times,altered,window=4,horizon=3)
    assert [x.future_log_return for x in base[:-1]] == pytest.approx(
        [x.future_log_return for x in new[:-1]])
    assert base[-1].future_log_return != new[-1].future_log_return
    assert base[-1].representation == new[-1].representation
