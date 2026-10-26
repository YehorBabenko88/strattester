"""Independent finite-difference input gradient oracle for small structural models."""
import pytest

import torch
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model


@pytest.mark.parametrize("recycles",[0,1])
def test_input_gradient_matches_central_difference(recycles):
    torch.manual_seed(993)
    model=build_structural_model(StructuralConfig(recycles=recycles)).double().eval()
    x=torch.randn(1,2,3,3,dtype=torch.float64,requires_grad=True)
    mask=torch.ones(1,2,3,dtype=torch.bool)
    value=model(x,mask)[:,0].sum()
    grad=torch.autograd.grad(value,x)[0]
    eps=1e-5
    for index in [(0,0,0,0),(0,1,1,2),(0,0,2,1)]:
        positive=x.detach().clone()
        negative=x.detach().clone()
        positive[index]+=eps
        negative[index]-=eps
        with torch.no_grad():
            numerical=(model(positive,mask)[:,0].sum()-model(negative,mask)[:,0].sum())/(2*eps)
        torch.testing.assert_close(grad[index],numerical,rtol=5e-3,atol=1e-5)


def test_masked_input_gradient_exact_zero():
    torch.manual_seed(994)
    model=build_structural_model(StructuralConfig(recycles=2)).double()
    x=torch.randn(1,2,3,3,dtype=torch.float64,requires_grad=True)
    mask=torch.tensor([[[1,1,1],[1,0,0]]],dtype=torch.bool)
    model(x,mask).sum().backward()
    assert torch.count_nonzero(x.grad[~mask])==0
    assert torch.isfinite(x.grad).all()
