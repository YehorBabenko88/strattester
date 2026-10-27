"""Explicit scalar attention oracle, independent of subject einsum/softmax path."""
import math
import pytest

torch=pytest.importorskip("torch")
from strattester.research.alphafold_triangle_attention import build_triangle_attention


@pytest.mark.parametrize("ending",[False,True])
def test_triangle_attention_scalar_reference(ending):
    torch.manual_seed(6200)
    op=build_triangle_attention(4,2)[int(ending)].double().eval()
    pair=torch.randn(1,3,3,4,dtype=torch.float64,requires_grad=True)
    mask=torch.tensor([[[1,1,0],[1,1,1],[0,1,1]]],dtype=torch.bool)
    z=pair.transpose(1,2) if ending else pair
    m=mask.transpose(1,2) if ending else mask
    z=op.norm(z)
    q=op.q(z).reshape(1,3,3,2,2)
    k=op.k(z).reshape(1,3,3,2,2)
    v=op.v(z).reshape(1,3,3,2,2)
    bias=op.bias(z)
    expected=torch.zeros((1,3,3,4),dtype=torch.float64)
    for origin in range(3):
        for query in range(3):
            if not m[0,origin,query]:
                continue
            values=[]
            for head in range(2):
                keys=[key for key in range(3) if m[0,origin,key]]
                if keys:
                    scores=torch.stack([(q[0,origin,query,head]*k[0,origin,key,head]).sum()/math.sqrt(2)+bias[0,query,key,head] for key in keys])
                    weights=torch.softmax(scores,0)
                    values.extend([sum((weights[t]*v[0,origin,key,head,d] for t,key in enumerate(keys)),torch.zeros((),dtype=torch.float64)) for d in range(2)])
                else:
                    values.extend([torch.zeros((),dtype=torch.float64) for _ in range(2)])
            expected[0,origin,query]=op.output(torch.stack(values)*torch.sigmoid(op.gate(z[0,origin,query])))
    expected=expected*m.unsqueeze(-1)
    if ending:
        expected=expected.transpose(1,2)
    torch.testing.assert_close(op(pair,mask),expected,rtol=1e-10,atol=1e-10)


@pytest.mark.parametrize("ending",[False,True])
def test_triangle_attention_all_masked_zero(ending):
    op=build_triangle_attention(4,2)[int(ending)].double()
    x=torch.randn(1,3,3,4,dtype=torch.float64,requires_grad=True)
    y=op(x,torch.zeros(1,3,3,dtype=torch.bool))
    assert torch.count_nonzero(y)==0
    y.sum().backward()
    assert x.grad is not None and torch.count_nonzero(x.grad)==0
