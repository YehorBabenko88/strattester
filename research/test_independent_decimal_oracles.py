import math
import random
import pytest
from research.independent_decimal_oracles import (
    decimal_returns, decimal_gaussian_nll, decimal_population_and_sample_volatility)
from research.math_contract_reference import log_returns, sample_volatility
from strattester.research.financial_evaluation import gaussian_scores

def test_decimal_log_and_simple_return_oracle():
    for prices in ([100, 110, 99], [1e-100, 1e100, 1e-100], [1, 1, 1]):
        expected = decimal_returns(prices)
        observed = log_returns(prices)
        for (log_r, simple_r), actual in zip(expected, observed):
            assert actual == pytest.approx(float(log_r), abs=1e-12)
            if abs(float(log_r)) < 600:
                assert math.expm1(actual) == pytest.approx(float(simple_r), rel=1e-10, abs=1e-12)

def test_volatility_population_vs_sample_explicit():
    data = [-0.02, 0.01, 0.04]
    population, sample = decimal_population_and_sample_volatility(data)
    assert sample_volatility(data) == pytest.approx(float(sample), rel=1e-12)
    assert float(sample) > float(population)

def test_gaussian_nll_decimal_oracle():
    for mu, sigma, y in [(0, 1, 0), (0.01, 0.3, -0.2), (-1, 2, 3)]:
        observed = gaussian_scores([mu], [sigma], [y])['nll']
        assert observed == pytest.approx(float(decimal_gaussian_nll(mu, sigma, y)), rel=1e-12)

def test_scale_invariance_metamorphic():
    rng = random.Random(1234)
    for _ in range(100):
        prices = [math.exp(rng.uniform(-8, 8)) for _ in range(8)]
        factor = math.exp(rng.uniform(-5, 5))
        before = log_returns(prices)
        after = log_returns([p * factor for p in prices])
        assert after == pytest.approx(before, abs=1e-13)
