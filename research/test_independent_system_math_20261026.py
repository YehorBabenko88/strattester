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
    assert base[-1].target_timestamp == times[-2]  # observed exclusive range; last possible label omitted


def test_pit_negative_future_and_duplicate():
    row = dict(event_id='x',event_time_ns=1,available_time_ns=10,bucket_end_ns=9,
               eligible=True,quality_status='VERIFIED',gap_status='NONE')
    assert validate_observations([row],10,9)
    with pytest.raises(ValueError):
        validate_observations([row],9,9)
    with pytest.raises(ValueError):
        validate_observations([row,row],10,9)
