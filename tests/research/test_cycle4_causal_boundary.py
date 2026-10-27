"""Independent financial structural causal-boundary regressions.

These checks apply to one-origin forecasts, not historical per-token predictions.
"""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.financial_structural_model import StructuralConfig, build_structural_model


@pytest.mark.parametrize("recycles", [0, 1, 2])
def test_masked_future_suffix_cannot_affect_origin_forecast(recycles):
    torch.manual_seed(4100 + recycles)
    model = build_structural_model(StructuralConfig(recycles=recycles)).double().eval()
    x = torch.randn(1, 3, 4, 3, dtype=torch.float64)
    mask = torch.tensor([[[1, 1, 1, 0], [1, 1, 0, 0], [1, 1, 1, 0]]], dtype=torch.bool)
    modified = x.clone()
    modified[~mask] = 1e25
    with torch.no_grad():
        a = model(x, mask)
        b = model(modified, mask)
    torch.testing.assert_close(a, b, rtol=0, atol=0)


@pytest.mark.parametrize("recycles", [0, 1])
def test_context_order_does_not_change_fixed_target(recycles):
    torch.manual_seed(4200 + recycles)
    model = build_structural_model(StructuralConfig(recycles=recycles)).double().eval()
    x = torch.randn(1, 3, 4, 3, dtype=torch.float64)
    mask = torch.ones(1, 3, 4, dtype=torch.bool)
    with torch.no_grad():
        a = model(x, mask)
        b = model(x[:, [0, 2, 1]], mask[:, [0, 2, 1]])
    torch.testing.assert_close(a, b, rtol=1e-9, atol=1e-9)


def test_masked_context_has_zero_input_gradient():
    torch.manual_seed(4300)
    model = build_structural_model(StructuralConfig(recycles=1)).double()
    x = torch.randn(1, 2, 4, 3, dtype=torch.float64, requires_grad=True)
    mask = torch.tensor([[[1, 1, 1, 1], [1, 1, 0, 0]]], dtype=torch.bool)
    model(x, mask).sum().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()
    assert torch.count_nonzero(x.grad[~mask]) == 0
