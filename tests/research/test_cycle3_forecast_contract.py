"""One-origin financial forecasting and target identity regression contracts.

No live data, checkpoint serialization, database or network operations.
"""
import pytest

torch=pytest.importorskip("torch")
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model


def test_explicit_target_identity_is_semantically_significant():
    torch.manual_seed(9301)
    model=build_structural_model(StructuralConfig(recycles=1)).double().eval()
    x=torch.randn(1,3,4,3,dtype=torch.float64)
    mask=torch.ones(1,3,4,dtype=torch.bool)
    with torch.no_grad():
        a=model(x,mask)
        b=model(x[:,[1,0,2]],mask[:,[1,0,2]])
    assert not torch.equal(a,b)


def test_masked_suffix_does_not_change_origin_prediction():
    torch.manual_seed(9302)
    model=build_structural_model(StructuralConfig(recycles=2)).double().eval()
    x=torch.randn(1,2,4,3,dtype=torch.float64)
    mask=torch.tensor([[[1,1,1,0],[1,1,1,0]]],dtype=torch.bool)
    changed=x.clone()
    changed[:,:,3]=1e25
    with torch.no_grad():
        torch.testing.assert_close(model(x,mask),model(changed,mask),rtol=0,atol=0)


@pytest.mark.parametrize("recycles",[0,1,2])
def test_distribution_positive_finite_at_origin(recycles):
    torch.manual_seed(9303)
    model=build_structural_model(StructuralConfig(recycles=recycles)).double().eval()
    x=torch.randn(2,2,4,3,dtype=torch.float64)
    mask=torch.ones(2,2,4,dtype=torch.bool)
    out=model(x,mask)
    assert out.shape==(2,2)
    assert torch.isfinite(out).all()
    assert (out[:,1]>0).all()
