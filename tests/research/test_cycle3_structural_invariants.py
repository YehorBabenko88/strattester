"""Independent structural invariance checks for cycle3 financial candidate.

Offline synthetic-only; no database, checkpoint or network operations.
"""
import pytest

import torch
from strattester.research.financial_structural_model import StructuralConfig, build_structural_model


@pytest.mark.parametrize("recycles", [0, 1, 2])
def test_target_fixed_context_permutation_equivariance(recycles):
    torch.manual_seed(2001)
    model = build_structural_model(StructuralConfig(recycles=recycles)).double().eval()
    x = torch.randn(1, 4, 4, 3, dtype=torch.float64)
    mask = torch.tensor([[[1, 1, 1, 1], [1, 1, 0, 0],
                          [1, 1, 1, 0], [1, 0, 0, 0]]], dtype=torch.bool)
    with torch.no_grad():
        expected = model(x, mask)
        observed = model(x[:, [0, 3, 1, 2]], mask[:, [0, 3, 1, 2]])
    torch.testing.assert_close(observed, expected, rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("recycles", [0, 1, 2])
def test_unavailable_context_perturbation_no_effect(recycles):
    torch.manual_seed(2002)
    model = build_structural_model(StructuralConfig(recycles=recycles)).double().eval()
    x = torch.randn(1, 3, 4, 3, dtype=torch.float64)
    mask = torch.tensor([[[1,1,1,1],[1,1,0,0],[0,0,0,0]]],dtype=torch.bool)
    changed=x.clone()
    changed[~mask]=1e30
    with torch.no_grad():
        a=model(x,mask)
        b=model(changed,mask)
    torch.testing.assert_close(a,b,rtol=0,atol=0)


@pytest.mark.parametrize("recycles", [0, 1, 2])
def test_active_gradients_and_deterministic_eval(recycles):
    torch.manual_seed(2003)
    model=build_structural_model(StructuralConfig(recycles=recycles)).double().eval()
    x=torch.randn(1,2,3,3,dtype=torch.float64,requires_grad=True)
    mask=torch.ones(1,2,3,dtype=torch.bool)
    first=model(x,mask)
    second=model(x,mask)
    torch.testing.assert_close(first,second,rtol=0,atol=0)
    first.sum().backward()
    assert torch.isfinite(x.grad).all()
    for name, parameter in model.named_parameters():
        if recycles == 0 and name.startswith(("recycle_msa.", "recycle_pair.")):
            assert parameter.grad is None, f"unexpected inactive gradient: {name}"
        else:
            assert parameter.grad is not None, f"missing active gradient: {name}"
            assert torch.isfinite(parameter.grad).all(), f"nonfinite gradient: {name}"


def test_equations_version_rejected_before_module_allocation(monkeypatch):
    monkeypatch.setattr(torch.nn,"Linear",lambda *a,**k: pytest.fail("allocated before version check"))
    with pytest.raises(ValueError,match="equations version"):
        build_structural_model(StructuralConfig(model_equations_version=1))
