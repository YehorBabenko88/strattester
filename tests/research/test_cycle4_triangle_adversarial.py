"""Adversarial finite-difference gradient and extreme-value triangle tests."""
import pytest

torch=pytest.importorskip("torch")
from strattester.research.alphafold_triangle import build_triangle_updates


@pytest.mark.parametrize("incoming",[False,True])
def test_triangle_central_difference_input_gradient(incoming):
    torch.manual_seed(412)
    op=build_triangle_updates(4,3)[int(incoming)].double().eval()
    x=torch.randn(1,3,3,4,dtype=torch.float64,requires_grad=True)
    mask=torch.tensor([[[1,1,0],[1,1,1],[0,1,1]]],dtype=torch.bool)
    grad=torch.autograd.grad(op(x,mask).square().sum(),x)[0]
    step=1e-5
    for idx in [(0,0,0,0),(0,1,2,3),(0,2,1,1)]:
        pos=x.detach().clone();neg=x.detach().clone()
        pos[idx]+=step;neg[idx]-=step
        with torch.no_grad():
            expected=(op(pos,mask).square().sum()-op(neg,mask).square().sum())/(2*step)
        torch.testing.assert_close(grad[idx],expected,rtol=1e-3,atol=1e-5)


@pytest.mark.parametrize("incoming",[False,True])
def test_triangle_finite_large_input_output_and_gradients(incoming):
    torch.manual_seed(413)
    op=build_triangle_updates(4,3)[int(incoming)].double()
    x=(torch.randn(1,3,3,4,dtype=torch.float64)*1e6).requires_grad_()
    out=op(x,torch.ones(1,3,3,dtype=torch.bool))
    assert torch.isfinite(out).all()
    out.sum().backward()
    assert torch.isfinite(x.grad).all()


@pytest.mark.parametrize("incoming",[False,True])
def test_triangle_nonfinite_input_rejected(incoming):
    op=build_triangle_updates(4,3)[int(incoming)]
    x=torch.zeros(1,3,3,4)
    x[0,1,2,3]=float("inf")
    with pytest.raises(ValueError,match="nonfinite"):
        op(x)
