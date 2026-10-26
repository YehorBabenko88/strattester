"""Pinned-upstream triangle equation differential, independent scalar reference.

The oracle does not invoke production einsum, gates, normalization or projection.
"""
import pytest

torch=pytest.importorskip("torch")
from strattester.research.alphafold_triangle import build_triangle_updates


@pytest.mark.parametrize("incoming",[False,True])
@pytest.mark.parametrize("dtype",[torch.float32,torch.float64])
def test_pinned_upstream_triangle_orientation_scalar_oracle(incoming,dtype):
    torch.manual_seed(2468)
    op=build_triangle_updates(4,3)[int(incoming)].to(dtype)
    x=torch.randn(1,3,3,4,dtype=dtype,requires_grad=True)
    mask=torch.tensor([[[1,1,0],[1,1,1],[0,1,1]]],dtype=torch.bool)
    z=op.norm(x)
    a=op.left(z)*torch.sigmoid(op.left_gate(z))
    b=op.right(z)*torch.sigmoid(op.right_gate(z))
    mixed=torch.zeros((1,3,3,3),dtype=dtype)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                if incoming:
                    if mask[0,k,j] and mask[0,k,i]:
                        mixed[0,i,j]+=a[0,k,j]*b[0,k,i]
                elif mask[0,i,k] and mask[0,j,k]:
                    mixed[0,i,j]+=a[0,i,k]*b[0,j,k]
    expected=op.output(op.center_norm(mixed))*torch.sigmoid(op.output_gate(z))
    expected=expected*mask.unsqueeze(-1)
    actual=op(x,mask)
    tol=1e-5 if dtype==torch.float32 else 1e-10
    torch.testing.assert_close(actual,expected,rtol=tol,atol=tol)
    actual.square().sum().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()


@pytest.mark.parametrize("incoming",[False,True])
def test_all_masked_triangle_output_and_input_gradient_zero(incoming):
    op=build_triangle_updates(4,3)[int(incoming)].double()
    x=torch.randn(1,3,3,4,dtype=torch.float64,requires_grad=True)
    output=op(x,torch.zeros(1,3,3,dtype=torch.bool))
    assert torch.count_nonzero(output)==0
    output.sum().backward()
    assert x.grad is not None and torch.count_nonzero(x.grad)==0


def test_triangle_resource_preflight():
    op=build_triangle_updates(4,3,max_pair_elements=35)[0]
    with pytest.raises(ValueError,match="budget"):
        op(torch.zeros(1,3,3,4))
