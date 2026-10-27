"""Independent explicit-loop OPM differential and mask-gradient checks."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_outer_product import build_outer_product_mean


def test_opm_masked_scalar_reference():
    torch.manual_seed(5901)
    model = build_outer_product_mean(4, 5, 3).double()
    x = torch.randn(1, 2, 3, 4, dtype=torch.float64, requires_grad=True)
    mask = torch.tensor([[[1, 1, 0], [1, 0, 1]]], dtype=torch.bool)
    z = model.norm(x)
    left = model.left(z)
    right = model.right(z)
    reference = torch.zeros((1, 3, 3, 9), dtype=torch.float64)
    counts = torch.zeros((1, 3, 3), dtype=torch.float64)
    for i in range(3):
        for j in range(3):
            for s in range(2):
                if mask[0, s, i] and mask[0, s, j]:
                    counts[0, i, j] += 1
                    for a in range(3):
                        for b in range(3):
                            reference[0, i, j, a*3+b] += left[0,s,i,a]*right[0,s,j,b]
            if counts[0,i,j]:
                reference[0,i,j] /= counts[0,i,j]
    expected = model.output(reference)*(counts>0).unsqueeze(-1)
    actual = model(x,mask)
    torch.testing.assert_close(actual,expected,rtol=1e-10,atol=1e-10)
    actual.square().sum().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()
    assert torch.count_nonzero(x.grad[~mask]) == 0


def test_opm_all_masked_zero_output_and_gradients():
    model = build_outer_product_mean(4, 5, 3).double()
    x = torch.randn(1,2,3,4,dtype=torch.float64,requires_grad=True)
    result = model(x,torch.zeros(1,2,3,dtype=torch.bool))
    assert torch.count_nonzero(result)==0
    result.sum().backward()
    assert x.grad is not None and torch.count_nonzero(x.grad)==0
