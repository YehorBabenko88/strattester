import pytest
import torch
from strattester.research.financial_structural_model import StructuralConfig, build_structural_model, build_column_attention


def inputs():
    torch.manual_seed(9)
    return torch.randn(2,2,4,3),torch.tensor([[[1,1,1,0],[1,1,1,0]]]*2,dtype=torch.bool)


def test_connected_mechanisms_execute_and_receive_finite_gradients():
    torch.manual_seed(7)
    model=build_structural_model(StructuralConfig(recycles=1))
    calls={}
    handles=[]
    for name,module in model.named_modules():
        if name.endswith(('row','column','outer','mul_out','mul_in','att_start','att_end','transition')):
            handles.append(module.register_forward_hook(lambda m,a,o,n=name:calls.__setitem__(n,calls.get(n,0)+1)))
    x,mask=inputs(); result=model(x,mask)
    assert result.shape==(2,2) and torch.all(result[:,1]>0) and torch.isfinite(result).all()
    loss=(result[:,0]-.2).square().mean()+result[:,1].mean()
    loss.backward()
    assert len(calls)>=9 and all(n==2 for n in calls.values())
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    assert any(torch.count_nonzero(p.grad) for p in model.parameters())
    for h in handles:h.remove()


def test_future_unavailable_values_cannot_affect_any_recycling_prediction():
    torch.manual_seed(7); model=build_structural_model(StructuralConfig(recycles=2))
    x,mask=inputs(); changed=x.clone(); changed[~mask]=1e6
    torch.testing.assert_close(model(x,mask),model(changed,mask),rtol=0,atol=0)


def test_recycling_reuses_learned_operators_and_changes_prediction():
    torch.manual_seed(7); a=build_structural_model(StructuralConfig(recycles=0))
    torch.manual_seed(7); b=build_structural_model(StructuralConfig(recycles=1))
    x,m=inputs()
    assert not torch.equal(a(x,m),b(x,m))


def test_resource_preflight_blocks_track_expansion_before_projection():
    model=build_structural_model(StructuralConfig(max_tracks=2))
    entered=[]; h=model.input.register_forward_pre_hook(lambda *a:entered.append(True))
    with pytest.raises(ValueError,match='budget'):model(torch.zeros(1,3,4,3),torch.ones(1,3,4))
    assert not entered;h.remove()


@pytest.mark.parametrize('cfg',[StructuralConfig(hidden=100000),StructuralConfig(max_parameters=1),StructuralConfig(recycles=1000)])
def test_constructor_rejects_unbounded_parameters_before_allocation(cfg,monkeypatch):
    monkeypatch.setattr(torch.nn,'Linear',lambda *a,**k:pytest.fail('allocation before admission'))
    with pytest.raises(ValueError):build_structural_model(cfg)


@pytest.mark.parametrize('kind',['nan','mask','empty','dtype'])
def test_invalid_tensor_contract(kind):
    model=build_structural_model(StructuralConfig());x,m=inputs()
    if kind=='nan':x[0,0,0,0]=float('nan')
    if kind=='mask':m=m.float();m[0,0,0]=.5
    if kind=='empty':x=x[:0];m=m[:0]
    if kind=='dtype':x=x.double()
    with pytest.raises(ValueError):model(x,m)


def test_column_attention_explicit_track_oracle_and_mask():
    torch.manual_seed(17); col=build_column_attention(4,2).double()
    x=torch.randn(1,3,2,4,dtype=torch.float64)
    mask=torch.tensor([[[1,1],[1,0],[0,0]]],dtype=torch.bool)
    z=col.norm(x); q,k,v=col.qkv(z).reshape(1,3,2,3,2,2).unbind(3)
    expected=torch.zeros_like(x)
    for n in range(2):
        for s in range(3):
            if not mask[0,s,n]:continue
            heads=[]
            valid=[t for t in range(3) if mask[0,t,n]]
            for h in range(2):
                scores=torch.stack([(q[0,s,n,h]*k[0,t,n,h]).sum()/2**.5 for t in valid])
                weights=scores.softmax(0)
                heads.append(sum(weights[j]*v[0,t,n,h] for j,t in enumerate(valid)))
            attended=torch.cat(heads)*torch.sigmoid(col.gate(z[0,s,n]))
            expected[0,s,n]=col.output(attended)
    torch.testing.assert_close(col(x,mask),expected,rtol=1e-10,atol=1e-10)
