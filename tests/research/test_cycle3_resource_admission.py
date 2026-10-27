"""Adversarial structural workspace and parameter admission tests."""
import pytest

import torch
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model


@pytest.mark.parametrize("field,value",[
    ("max_batch",33),("max_tracks",65),("max_tokens",257),
    ("depth",9),("recycles",5),("hidden",129),("intermediate",65),
])
def test_configuration_limits_fail_before_allocation(field,value,monkeypatch):
    kwargs={field:value}
    monkeypatch.setattr(torch.nn,"Linear",lambda *a,**k:pytest.fail("allocation before config rejection"))
    with pytest.raises(ValueError):
        build_structural_model(StructuralConfig(**kwargs))


def test_workspace_budget_rejected_before_projection():
    model=build_structural_model(StructuralConfig(max_work_bytes=1_100_000,recycles=2))
    called=[]
    hook=model.input.register_forward_pre_hook(lambda *a:called.append(True))
    with pytest.raises(ValueError,match="workspace budget"):
        model(torch.ones(2,2,16,3),torch.ones(2,2,16,dtype=torch.bool))
    hook.remove()
    assert not called


def test_wrong_dtype_rejected_before_projection():
    model=build_structural_model()
    called=[]
    hook=model.input.register_forward_pre_hook(lambda *a:called.append(True))
    with pytest.raises(ValueError,match="dtype"):
        model(torch.ones(1,2,3,3,dtype=torch.float64),torch.ones(1,2,3,dtype=torch.bool))
    hook.remove()
    assert not called
