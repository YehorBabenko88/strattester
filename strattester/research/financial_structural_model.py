"""Connected financial structural adaptation; NOT original AlphaFold inference.

Each call predicts at ONE origin using a window whose mask was validated by
the snapshot boundary. Historical positions may exchange information inside
that origin's available window. This is not a per-position streaming forecast.
No biological code or weights are imported; reference: pinned upstream modules.py.
"""
from dataclasses import dataclass
from .financial_contract import integer
from .financial_torch_runtime import serialize_cpu_research,cpu_research_state
from contextlib import nullcontext


@dataclass(frozen=True)
class StructuralConfig:
    # Version 2 corrects incoming triangle projection orientation. Legacy
    # checkpoint configs must not default silently to these new equations.
    model_equations_version: int = 2
    input_channels: int = 3
    horizon_ns: int = 120
    hidden: int = 8
    heads: int = 2
    intermediate: int = 4
    depth: int = 1
    recycles: int = 1
    max_batch: int = 8
    max_tracks: int = 16
    max_tokens: int = 32
    max_parameters: int = 2_000_000
    max_work_bytes: int = 128*1024*1024

    def validate(self):
        if type(self.model_equations_version) is not int or self.model_equations_version != 2:
            raise ValueError('unsupported model equations version')
        for name,value in self.__dict__.items(): integer(value,name,0 if name=='recycles' else 1)
        if (self.hidden%self.heads or self.max_tokens<2 or self.max_tokens>256
            or self.depth>8 or self.recycles>4 or self.input_channels>128
            or self.hidden>128 or self.intermediate>64 or self.max_tracks>64 or self.max_batch>32
            or self.max_parameters>2_000_000 or self.max_work_bytes>512*1024*1024):
            raise ValueError('invalid structural configuration')
        # Conservative parameter bound includes every imported projection and
        # transitions. Checked before any nn.Module with parameters is created.
        upper=self.depth*(512*self.hidden**2+8*self.intermediate**2*self.hidden)+self.input_channels*self.hidden+32*self.hidden
        if upper>self.max_parameters or upper*4*8>self.max_work_bytes:
            raise ValueError('structural parameter budget exceeded')
        return self


def build_column_attention(channels, heads):
    integer(channels,'channels',1);integer(heads,'heads',1)
    if channels%heads or channels>256: raise ValueError('column dimensions/budget')
    import torch
    from torch import nn

    class ColumnAttention(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm=nn.LayerNorm(channels)
            self.qkv=nn.Linear(channels,channels*3,bias=False)
            self.gate=nn.Linear(channels,channels)
            self.output=nn.Linear(channels,channels)

        def forward(self,msa,mask):
            b,s,n,c=msa.shape
            if c!=channels or min(b,s,n)<1 or b*n*heads*s*s>2_000_000:
                raise ValueError('column shape/budget')
            if mask.shape!=(b,s,n) or not ((mask==0)|(mask==1)).all(): raise ValueError('column mask')
            if not torch.isfinite(msa).all(): raise ValueError('nonfinite column input')
            z=self.norm(msa)
            q,k,v=self.qkv(z).reshape(b,s,n,3,heads,c//heads).unbind(3)
            scores=torch.einsum('bsnhd,btnhd->bnhst',q,k)*(c//heads)**-.5
            valid=mask.permute(0,2,1)[:, :, None, None, :].bool()
            weights=scores.masked_fill(~valid,torch.finfo(scores.dtype).min).softmax(-1)*valid
            weights=weights/weights.sum(-1,keepdim=True).clamp_min(torch.finfo(weights.dtype).tiny)
            attended=torch.einsum('bnhst,btnhd->bsnhd',weights,v).reshape(b,s,n,c)
            return self.output(attended*torch.sigmoid(self.gate(z)))*mask.unsqueeze(-1)
    return ColumnAttention()


@serialize_cpu_research
def build_structural_model(config=StructuralConfig(),*,seed=None):
    config.validate()
    import torch
    from torch import nn
    from .alphafold_msa_attention import build_msa_row_attention
    from .alphafold_outer_product import build_outer_product_mean
    from .alphafold_pair_stack import build_pair_stack
    h=config.hidden

    class StructuralLayer(nn.Module):
        def __init__(self):
            super().__init__()
            self.row=build_msa_row_attention(h,h,config.heads)
            self.column=build_column_attention(h,config.heads)
            self.msa_norm=nn.LayerNorm(h)
            self.msa_transition=nn.Sequential(nn.Linear(h,h*4),nn.ReLU(),nn.Linear(h*4,h))
            self.outer=build_outer_product_mean(h,h,config.intermediate)
            self.pair_stack=build_pair_stack(h,config.heads,depth=1,intermediate=config.intermediate,max_tokens=config.max_tokens)

        def forward(self,msa,pair,mask,pair_mask):
            msa=(msa+self.row(msa,pair,mask))*mask.unsqueeze(-1)
            msa=(msa+self.column(msa,mask))*mask.unsqueeze(-1)
            msa=(msa+self.msa_transition(self.msa_norm(msa)))*mask.unsqueeze(-1)
            pair=self.pair_stack(pair+self.outer(msa,mask),pair_mask)
            return msa,pair

    class FinancialStructuralModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.config=config
            self.input=nn.Linear(config.input_channels,h)
            self.layers=nn.ModuleList(StructuralLayer() for _ in range(config.depth))
            self.recycle_msa=nn.LayerNorm(h)
            self.recycle_pair=nn.LayerNorm(h)
            self.single=nn.Linear(h,h)
            self.head=nn.Linear(2*h,2)

        def forward(self,features,mask):
            if features.ndim!=4 or mask.shape!=features.shape[:3]: raise ValueError('expected [B,S,N,C] with matching mask')
            b,s,n,c=features.shape
            if (not 1<=b<=config.max_batch or not 1<=s<=config.max_tracks
                or not 2<=n<=config.max_tokens or c!=config.input_channels):
                raise ValueError('structural shape budget exceeded')
            parameter=next(self.parameters())
            if (features.dtype not in (torch.float32,torch.float64) or features.device.type!='cpu'
                or features.dtype!=parameter.dtype or features.device!=parameter.device or mask.device!=features.device):
                raise ValueError('matching model dtype/device required')
            track=b*s*n*h; pair=b*n*n*h; outer=b*n*n*config.intermediate**2
            attention=max(b*s*config.heads*n*n,b*n*config.heads*s*s,b*config.heads*n**3)
            if max(track,pair,outer,attention,b*n*n*max(h,config.intermediate))>2_000_000:
                raise ValueError('imported structural operator budget exceeded')
            estimate=(8*track+8*pair+2*outer+4*attention)*features.element_size()*8*config.depth*(config.recycles+1)
            if estimate>config.max_work_bytes: raise ValueError('structural workspace budget exceeded')
            if not torch.isfinite(features).all() or not ((mask==0)|(mask==1)).all(): raise ValueError('nonfinite features or nonbinary mask')
            mask=mask.bool()
            if not mask[:,0].any(dim=1).all(): raise ValueError('empty target-track available window')
            # Zero unavailable inputs BEFORE normalization/projection. Every pair
            # operator receives endpoints derived only from this available set.
            base=self.input(features*mask.unsqueeze(-1))*mask.unsqueeze(-1)
            valid=mask.any(1)
            pm=valid[:,:,None]&valid[:,None,:]
            msa=base
            pair=features.new_zeros(b,n,n,h)
            for recycle in range(config.recycles+1):
                if recycle:
                    msa=base+self.recycle_msa(msa)*mask.unsqueeze(-1)
                    pair=self.recycle_pair(pair)*pm.unsqueeze(-1)
                for layer in self.layers: msa,pair=layer(msa,pair,mask,pm)
            # Track zero is the declared target instrument; context tracks
            # affect it through column attention and pair exchange.
            single=self.single(msa[:,0])
            # Last available token, not an arbitrary padded/future suffix.
            indices=(torch.arange(n,device=features.device)[None,:]*mask[:,0]).max(1).values
            batch=torch.arange(b,device=features.device)
            pooled_pair=(pair[batch,indices]*valid.unsqueeze(-1)).sum(1)/valid.sum(1).unsqueeze(-1)
            raw=self.head(torch.cat((single[batch,indices],pooled_pair),-1))
            result=torch.stack((raw[:,0],torch.nn.functional.softplus(raw[:,1]).clamp(1e-5,10.)),-1)
            if not torch.isfinite(result).all(): raise ValueError('nonfinite financial distribution')
            return result
    with cpu_research_state(seed=seed) if seed is not None else nullcontext():
        return FinancialStructuralModel()
