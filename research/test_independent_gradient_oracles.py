import math
import pytest
from research.independent_gradient_oracles import central_difference, gaussian_nll_gradient

def nll(values):
    mu, sigma = values
    target = 0.7
    return math.log(sigma) + 0.5 * ((target-mu)/sigma)**2 + 0.5*math.log(2*math.pi)

@pytest.mark.parametrize("mu,sigma", [(0.,1.),(.3,.7),(-.5,2.)])
def test_gaussian_gradient_vs_finite_difference(mu, sigma):
    expected = gaussian_nll_gradient(mu, sigma, .7)
    for i in range(2):
        assert central_difference(nll, (mu,sigma), i, step=1e-6) == pytest.approx(expected[i], rel=1e-7, abs=1e-8)

def test_invalid_gradient_request_fails_closed():
    with pytest.raises(ValueError):
        central_difference(nll, (0.,1.), 1, step=0)
    with pytest.raises(ValueError):
        gaussian_nll_gradient(0,0,1)
