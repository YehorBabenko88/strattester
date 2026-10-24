"""Differential checks at pinned PR21 implementation, independent index oracles."""
import pytest

torch = pytest.importorskip("torch")
from research.upstream_mechanism_reference import (
    outer_product_reference, triangle_reference, attention_reference,
)
from strattester.research.alphafold_outer_product import build_outer_product_mean
from strattester.research.alphafold_triangle import build_triangle_updates
from strattester.research.financial_structural_model import build_column_attention


def test_opm_differential_masked_double():
    torch.manual_seed(101)
    module=build_outer_product_mean(4,5,3).double()
    x=torch.randn(1,2,3,4,dtype=torch.float64)
    mask=torch.tensor([[[1,1,0],[1,0,1]]],dtype=torch.bool)
    z=module.norm(x)
    left=module.left(z)[0]
    right=module.right(z)[0]
    ref=outer_product_reference(left,right,mask[0])
    counts=torch.einsum("si,sj->ij",mask[0].double(),mask[0].double())
    expected=module.output(ref.reshape(1,3,3,9))*(counts>0)[None,:,:,None]
    torch.testing.assert_close(module(x,mask),expected,rtol=1e-10,atol=1e-10)


@pytest.mark.parametrize("incoming", [False,True])
def test_triangle_differential_masked_double(incoming):
    torch.manual_seed(102)
    module=build_triangle_updates(4,3)[int(incoming)].double()
    x=torch.randn(1,3,3,4,dtype=torch.float64)
    mask=torch.tensor([[[1,1,0],[1,1,1],[0,1,1]]],dtype=torch.bool)
    z=module.norm(x)
    left=module.left(z)*torch.sigmoid(module.left_gate(z))
    right=module.right(z)*torch.sigmoid(module.right_gate(z))
    ref=triangle_reference(left[0],right[0],mask[0],incoming=incoming)
    expected=module.output(module.center_norm(ref[None]))*torch.sigmoid(module.output_gate(z))
    expected=expected*mask.unsqueeze(-1)
    torch.testing.assert_close(module(x,mask),expected,rtol=1e-10,atol=1e-10)


def test_column_attention_independent_softmax_oracle():
    torch.manual_seed(103)
    module=build_column_attention(4,2).double()
    x=torch.randn(1,3,2,4,dtype=torch.float64)
    mask=torch.tensor([[[1,1],[1,0],[0,0]]],dtype=torch.bool)
    z=module.norm(x)
    q,k,v=module.qkv(z).reshape(1,3,2,3,2,2).unbind(3)
    ref=torch.zeros_like(x)
    for t in range(2):
        query=q[0,:,t]
        key=k[0,:,t]
        value=v[0,:,t]
        bias=torch.zeros(2,3,3,dtype=torch.float64)
        attended=attention_reference(query,key,value,bias,mask[0,:,t],mask[0,:,t]).reshape(3,4)
        ref[0,:,t]=module.output(attended*torch.sigmoid(module.gate(z[0,:,t])))*mask[0,:,t,None]
    torch.testing.assert_close(module(x,mask),ref,rtol=1e-10,atol=1e-10)
