"""Independent numerical checks for masked MSA-to-pair outer product."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_outer_product import build_outer_product_mean


def test_outer_product_explicit_reference_and_gradients():
    torch.manual_seed(81)
    module = build_outer_product_mean(4, 6, intermediate=3).double()
    msa = torch.randn(1, 2, 3, 4, dtype=torch.float64, requires_grad=True)
    mask = torch.tensor([[[1, 1, 0], [1, 0, 1]]], dtype=torch.float64)
    result = module(msa, mask)
    normalized = module.norm(msa)
    a = module.left(normalized)
    b = module.right(normalized)
    reference = torch.zeros(1, 3, 3, 3, 3, dtype=torch.float64)
    for i in range(3):
        for j in range(3):
            valid = [s for s in range(2) if mask[0, s, i] and mask[0, s, j]]
            if valid:
                for s in valid:
                    reference[0, i, j] += torch.outer(a[0, s, i], b[0, s, j])
                reference[0, i, j] /= len(valid)
    expected = module.output(reference.reshape(1, 3, 3, 9))
    expected = expected * torch.tensor([[[1, 1, 1], [1, 1, 0], [1, 0, 1]]], dtype=torch.float64).unsqueeze(-1)
    torch.testing.assert_close(result, expected, atol=1e-10, rtol=1e-10)
    result.square().mean().backward()
    assert msa.grad is not None and torch.isfinite(msa.grad).all()


def test_outer_product_mask_all_zero():
    module = build_outer_product_mean(4, 8, 3)
    output = module(torch.randn(1, 2, 3, 4), torch.zeros(1, 2, 3))
    assert torch.count_nonzero(output) == 0


def test_outer_product_resource_budget():
    module = build_outer_product_mean(4, 8, 4, max_elements=100)
    with pytest.raises(ValueError, match="budget"):
        module(torch.zeros(1, 2, 3, 4))
