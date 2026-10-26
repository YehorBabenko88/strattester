import math
import pytest
from research.independent_gaussian_stability import stable_gaussian_nll

def test_normal_gaussian_matches_analytic():
    assert stable_gaussian_nll(0.,1.,0.)==pytest.approx(.5*math.log(2*math.pi))
    assert stable_gaussian_nll(0.,2.,1.)==pytest.approx(math.log(2)+.125+.5*math.log(2*math.pi))

def test_overflow_rejected():
    with pytest.raises(ValueError,match='overflow'):
        stable_gaussian_nll(0.,1e-300,1e300)
    with pytest.raises(ValueError,match='overflow'):
        stable_gaussian_nll(0.,1.,1e200)

def test_nonfinite_rejected():
    with pytest.raises(ValueError):
        stable_gaussian_nll(0.,float('nan'),1.)
