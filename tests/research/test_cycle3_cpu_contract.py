"""Synthetic-only exact CPU model contract checks for disposable G1 preparation."""
import pytest

torch=pytest.importorskip("torch")
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model


@pytest.mark.parametrize("dtype",[torch.float32,torch.float64])
def test_cpu_forward_backward_dtype_contract(dtype):
    torch.manual_seed(7001)
    model=build_structural_model(StructuralConfig(recycles=1)).to(dtype=dtype).eval()
    x=torch.randn(1,2,4,3,dtype=dtype,requires_grad=True)
    mask=torch.ones(1,2,4,dtype=torch.bool)
    output=model(x,mask)
    assert output.shape==(1,2) and output.dtype==dtype
    assert torch.isfinite(output).all() and (output[:,1]>0).all()
    output.sum().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()


def test_target_all_masked_refused():
    model=build_structural_model()
    x=torch.zeros(1,2,3,3)
    mask=torch.ones(1,2,3,dtype=torch.bool)
    mask[:,0]=False
    with pytest.raises(ValueError,match="target-track"):
        model(x,mask)


def test_nonfinite_features_rejected_before_projection():
    model=build_structural_model()
    called=[]
    hook=model.input.register_forward_pre_hook(lambda *args:called.append(True))
    x=torch.zeros(1,2,3,3)
    x[0,0,0,0]=float("inf")
    with pytest.raises(ValueError,match="nonfinite"):
        model(x,torch.ones(1,2,3,dtype=torch.bool))
    hook.remove()
    assert not called
