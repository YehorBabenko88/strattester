"""Adversarial shape admission tests; no GPU or network required."""
import pytest
from strattester.research.alphafold_security import admit_pair_shape, PairBudget

@pytest.mark.parametrize("shape", [(0, 10, 8), (-1, 10, 8), (1, 1025, 8), (9, 10, 8), (True, 10, 8)])
def test_reject_invalid_or_oversized(shape):
    with pytest.raises(ValueError):
        admit_pair_shape(*shape)

def test_quadratic_memory_growth():
    a = admit_pair_shape(1, 16, 8)
    b = admit_pair_shape(1, 32, 8)
    assert b == 4 * a

def test_budget_fails_closed():
    with pytest.raises(ValueError):
        admit_pair_shape(1, 256, 32, budget=PairBudget(max_pair_bytes=1024))
