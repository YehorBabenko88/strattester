"""Adversarial financial structural model tests on pinned PR21-derived branch.

Tests do not access DB, network, trading services or external checkpoints.
"""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.financial_structural_model import StructuralConfig, build_structural_model
from strattester.research.alphafold_msa_attention import build_msa_row_attention


def _model(recycles=1):
    torch.manual_seed(900)
    return build_structural_model(StructuralConfig(recycles=recycles)).double().eval()


def test_context_permutation_invariance_same_target():
    model=_model()
    torch.manual_seed(901)
    x=torch.randn(1,3,4,3,dtype=torch.float64)
    mask=torch.ones(1,3,4,dtype=torch.bool)
    original=model(x,mask)
    order=[0,2,1]
    permuted=model(x[:,order],mask[:,order])
    torch.testing.assert_close(original,permuted,rtol=1e-9,atol=1e-9)


@pytest.mark.parametrize("recycles",[0,1,2])
def test_all_masked_context_cannot_change_forecast(recycles):
    model=_model(recycles)
    x=torch.randn(1,2,4,3,dtype=torch.float64)
    mask=torch.ones(1,2,4,dtype=torch.bool)
    mask[:,1]=False
    first=model(x,mask)
    changed=x.clone()
    changed[:,1]=1e20
    torch.testing.assert_close(first,model(changed,mask),rtol=0,atol=0)


@pytest.mark.parametrize("recycles",[0,1,2])
def test_finite_output_and_backward_at_moderate_extremes(recycles):
    model=_model(recycles)
    x=torch.full((1,2,3,3),1e3,dtype=torch.float64,requires_grad=True)
    mask=torch.ones(1,2,3,dtype=torch.bool)
    output=model(x,mask)
    assert torch.isfinite(output).all()
    output.sum().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()


def test_row_attention_causal_mode_prefix_invariance():
    torch.manual_seed(902)
    module=build_msa_row_attention(8,8,2).double().eval()
    msa=torch.randn(1,2,4,8,dtype=torch.float64)
    pair=torch.randn(1,4,4,8,dtype=torch.float64)
    modified=msa.clone()
    modified[:,:,3]+=1e5
    with torch.no_grad():
        a=module(msa,pair,causal=True)
        b=module(modified,pair,causal=True)
    torch.testing.assert_close(a[:,:,:3],b[:,:,:3],rtol=0,atol=0)


def test_target_identity_is_not_context_invariance():
    model=_model()
    x=torch.randn(1,2,4,3,dtype=torch.float64)
    mask=torch.ones(1,2,4,dtype=torch.bool)
    # The first track is the explicitly selected target, not a permutation-invariant pool.
    assert not torch.equal(model(x,mask),model(x.flip(1),mask.flip(1)))
