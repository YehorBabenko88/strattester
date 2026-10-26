"""Pair stack smoke, isolation, mask and gradient tests."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_pair_stack import build_pair_stack


def test_stack_gradients_and_mask():
    torch.manual_seed(31)
    model = build_pair_stack(channels=8, heads=2, depth=2, intermediate=12)
    pair = torch.randn(1, 4, 4, 8, requires_grad=True)
    mask = torch.ones(1, 4, 4)
    mask[:, 3, :] = 0
    output = model(pair, mask)
    assert output.shape == pair.shape
    assert torch.isfinite(output).all()
    assert torch.count_nonzero(output[:, 3]) == 0
    output.square().mean().backward()
    assert pair.grad is not None and torch.isfinite(pair.grad).all()


def test_stack_budget_and_nonfinite_fail_closed():
    model = build_pair_stack(channels=8, heads=2, max_tokens=3)
    with pytest.raises(ValueError, match="budget"):
        model(torch.zeros(1, 4, 4, 8))
    pair = torch.zeros(1, 3, 3, 8)
    pair[0, 1, 1, 0] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        model(pair)


def test_stack_reproducible_initialization():
    torch.manual_seed(52)
    first = build_pair_stack(channels=8, heads=2, depth=1)
    torch.manual_seed(52)
    second = build_pair_stack(channels=8, heads=2, depth=1)
    x = torch.randn(1, 3, 3, 8)
    torch.testing.assert_close(first(x), second(x), atol=0, rtol=0)
