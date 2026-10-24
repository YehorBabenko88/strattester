"""Independent Decimal oracles: no Grid/math implementation imported."""
from decimal import Decimal, localcontext
import math

def decimal_returns(prices):
    values = [Decimal(str(x)) for x in prices]
    if len(values) < 2 or any(not p.is_finite() or p <= 0 for p in values):
        raise ValueError("positive finite prices required")
    with localcontext() as ctx:
        ctx.prec = 70
        return [(b.ln() - a.ln(), b / a - 1) for a, b in zip(values, values[1:])]

def decimal_gaussian_nll(mu, sigma, y):
    m, s, target = map(lambda x: Decimal(str(x)), (mu, sigma, y))
    if not all(x.is_finite() for x in (m, s, target)) or s <= 0:
        raise ValueError("invalid Gaussian parameters")
    with localcontext() as ctx:
        ctx.prec = 70
        # Decimal pi constant, independently specified.
        pi = Decimal("3.141592653589793238462643383279502884197169399375105820974944")
        return s.ln() + ((target - m) / s) ** 2 / 2 + (2 * pi).ln() / 2

def decimal_population_and_sample_volatility(returns):
    values = [Decimal(str(x)) for x in returns]
    if len(values) < 2 or any(not v.is_finite() for v in values):
        raise ValueError("two finite returns required")
    with localcontext() as ctx:
        ctx.prec = 70
        mean = sum(values) / len(values)
        sq = sum((v - mean) ** 2 for v in values)
        return (sq / len(values)).sqrt(), (sq / (len(values) - 1)).sqrt()
