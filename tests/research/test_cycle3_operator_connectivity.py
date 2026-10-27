"""Structural model architecture and resource admission contract tests."""
import pytest

import torch
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model


def test_all_required_operators_connected_to_forecast():
    torch.manual_seed(9021)
    model=build_structural_model(StructuralConfig(depth=2,recycles=1)).double()
    calls={}
    hooks=[]
    for name,module in model.named_modules():
        if name.endswith(("row","column","outer","mul_out","mul_in","att_start","att_end","transition")):
            hooks.append(module.register_forward_hook(lambda m,a,o,key=name:calls.__setitem__(key,calls.get(key,0)+1)))
    x=torch.randn(1,2,3,3,dtype=torch.float64,requires_grad=True)
    result=model(x,torch.ones(1,2,3,dtype=torch.bool))
    result.sum().backward()
    for hook in hooks:hook.remove()
    assert len(calls)>=16
    assert all(v==2 for v in calls.values())
    assert torch.isfinite(x.grad).all()


@pytest.mark.parametrize("bad", [float("nan"),float("inf"),float("-inf")])
def test_nonfinite_mask_rejected(bad):
    model=build_structural_model()
    mask=torch.ones(1,2,3)
    mask[0,1,1]=bad
    with pytest.raises(ValueError):
        model(torch.zeros(1,2,3,3),mask)


def test_batch_budget_preprojection():
    model=build_structural_model(StructuralConfig(max_batch=1))
    called=[]
    hook=model.input.register_forward_pre_hook(lambda *a:called.append(True))
    with pytest.raises(ValueError,match="budget"):
        model(torch.zeros(2,2,3,3),torch.ones(2,2,3,dtype=torch.bool))
    hook.remove()
    assert not called
