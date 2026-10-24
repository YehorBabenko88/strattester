"""Synthetic-only CPU checkpoint readiness smoke test.

Verifies an optimizer update and deterministic tensor-only in-memory reload.
Does not create or publish a checkpoint artifact; no DB or network.
"""
import pytest

torch=pytest.importorskip("torch")
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model


def test_optimizer_update_and_in_memory_reload_equivalence():
    config=StructuralConfig(model_equations_version=2,recycles=1)
    torch.manual_seed(8123)
    model=build_structural_model(config).double()
    x=torch.randn(1,2,4,3,dtype=torch.float64)
    mask=torch.ones(1,2,4,dtype=torch.bool)
    target=torch.tensor([[0.03,0.12]],dtype=torch.float64)
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4)
    before={name:p.detach().clone() for name,p in model.named_parameters()}
    optimizer.zero_grad(set_to_none=True)
    prediction=model(x,mask)
    loss=(prediction-target).square().mean()
    assert torch.isfinite(loss)
    loss.backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
    optimizer.step()
    assert any(not torch.equal(before[name],p) for name,p in model.named_parameters())
    state={key:value.detach().clone() for key,value in model.state_dict().items()}
    torch.manual_seed(9999)
    restored=build_structural_model(config).double()
    restored.load_state_dict(state,strict=True)
    model.eval()
    restored.eval()
    with torch.no_grad():
        torch.testing.assert_close(model(x,mask),restored(x,mask),rtol=0,atol=0)


def test_equations_version_is_explicit_for_checkpoint_candidate():
    assert StructuralConfig().model_equations_version==2
    with pytest.raises(ValueError,match="equations version"):
        build_structural_model(StructuralConfig(model_equations_version=1))
