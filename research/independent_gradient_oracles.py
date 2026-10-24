"""Independent numerical finite-difference oracle, no autograd required."""
import math

def central_difference(function, values, index, *, step=1e-5):
    values = tuple(float(x) for x in values)
    if not values or not 0 <= index < len(values) or not math.isfinite(step) or step <= 0 or any(not math.isfinite(x) for x in values):
        raise ValueError("invalid derivative request")
    plus = list(values)
    minus = list(values)
    plus[index] += step
    minus[index] -= step
    a = float(function(tuple(plus)))
    b = float(function(tuple(minus)))
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError("nonfinite function value")
    return (a - b) / (2 * step)

def gaussian_nll_gradient(mu, sigma, target):
    if not all(math.isfinite(x) for x in (mu, sigma, target)) or sigma <= 0:
        raise ValueError("invalid distribution")
    return ((mu - target) / sigma**2, 1 / sigma - (target - mu)**2 / sigma**3)
