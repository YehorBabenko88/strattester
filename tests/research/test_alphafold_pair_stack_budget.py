"""Adversarial stack-level budget contract tests."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_pair_stack import build_pair_stack


def test_attention_budget_preflight_prevents_layer_execution():
    model = build_pair_stack(channels=8, heads=2, depth=1, max_tokens=64,
                             max_attention_elements=50)
    # 1 * 2 * 4**3 = 128 > 50
    with pytest.raises(ValueError, match="attention budget"):
        model(torch.zeros(1, 4, 4, 8))


def test_pair_intermediate_budget_preflight():
    model = build_pair_stack(channels=8, heads=2, depth=1, intermediate=16,
                             max_pair_elements=100)
    # 1 * 3**2 * 16 = 144 > 100
    with pytest.raises(ValueError, match="pair budget"):
        model(torch.zeros(1, 3, 3, 8))


def test_boundary_equal_budget_is_allowed():
    model = build_pair_stack(channels=8, heads=2, depth=1, intermediate=8,
                             max_attention_elements=54, max_pair_elements=72)
    result = model(torch.zeros(1, 3, 3, 8))
    assert result.shape == (1, 3, 3, 8)
    assert torch.isfinite(result).all()


def test_batch_size_changes_budget():
    model = build_pair_stack(channels=8, heads=2, depth=1, intermediate=8,
                             max_attention_elements=54)
    with pytest.raises(ValueError, match="attention budget"):
        model(torch.zeros(2, 3, 3, 8))
