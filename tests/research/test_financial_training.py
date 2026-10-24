import pytest
import torch
from strattester.research.financial_structural_model import StructuralConfig, build_structural_model
from strattester.research.financial_training import fit_structural, TrainingCancelled


def make_data():
    torch.manual_seed(20)
    return torch.randn(4,2,3,3),torch.tensor([.02,-.03,.01,.04]),torch.ones(4,2,3,dtype=torch.bool)


def test_optimizer_changes_weights_and_reproduces_seed():
    x,y,m=make_data(); outputs=[]
    for _ in range(2):
        torch.manual_seed(11); model=build_structural_model(StructuralConfig(recycles=0))
        before={n:p.detach().clone() for n,p in model.named_parameters()}
        losses=fit_structural(model,x,y,m,seed=11,steps=3)
        assert len(losses)==3 and all(torch.isfinite(torch.tensor(losses)))
        assert any(not torch.equal(before[n],p) for n,p in model.named_parameters())
        outputs.append(model(x,m).detach())
    torch.testing.assert_close(outputs[0],outputs[1],rtol=0,atol=0)


def test_cancelled_fit_rolls_back_entire_model():
    x,y,m=make_data();torch.manual_seed(11); model=build_structural_model(StructuralConfig(recycles=0))
    before={n:p.clone() for n,p in model.state_dict().items()};calls=[]
    def cancel(): calls.append(1);return len(calls)>1
    with pytest.raises(TrainingCancelled):fit_structural(model,x,y,m,steps=5,cancel=cancel)
    assert all(torch.equal(before[n],p) for n,p in model.state_dict().items())


@pytest.mark.parametrize('bad',[float('nan'),float('inf')])
def test_bad_label_does_not_update_model(bad):
    x,y,m=make_data();y[0]=bad;model=build_structural_model(StructuralConfig())
    with pytest.raises(ValueError):fit_structural(model,x,y,m,steps=2)


def test_training_bank_budget_rejected_before_state_copy():
    from dataclasses import replace
    x,y,m=make_data()
    model=build_structural_model(StructuralConfig(recycles=0))
    model.config=replace(model.config,max_work_bytes=2_000_000)
    # Expanded views carry a large logical bank without allocating its storage.
    x=torch.zeros(1,16,32,3).expand(1024,-1,-1,-1)
    y=torch.zeros(1024);m=torch.ones(1,16,32,dtype=torch.bool).expand(1024,-1,-1)
    with pytest.raises(ValueError,match='training bank budget'):
        fit_structural(model,x,y,m,steps=1)
