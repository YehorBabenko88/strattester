"""Research-only AlphaFold-style outer-product mean (MSA -> pair).

Input [B,S,N,Cm] is a set of aligned feature tracks. In financial use,
S must denote independently justified, time-aligned channels/observations,
not future bars or an invented biological MSA. No I/O or trading.
"""
from __future__ import annotations


def build_outer_product_mean(msa_channels: int, pair_channels: int,
                             intermediate: int = 16, *, max_elements: int = 2_000_000):
    if min(msa_channels, pair_channels, intermediate, max_elements) < 1:
        raise ValueError("invalid outer product dimensions")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("optional torch dependency required") from exc

    class OuterProductMean(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm = nn.LayerNorm(msa_channels)
            self.left = nn.Linear(msa_channels, intermediate)
            self.right = nn.Linear(msa_channels, intermediate)
            self.output = nn.Linear(intermediate * intermediate, pair_channels)

        def forward(self, msa, mask=None):
            if msa.ndim != 4 or msa.shape[-1] != msa_channels:
                raise ValueError("expected MSA [B,S,N,C]")
            b, s, n, _ = msa.shape
            if s < 1 or n < 2 or b * n * n * intermediate * intermediate > max_elements:
                raise ValueError("outer product budget exceeded")
            if not torch.isfinite(msa).all().item():
                raise ValueError("nonfinite MSA input")
            if mask is None:
                mask = torch.ones((b, s, n), device=msa.device, dtype=torch.bool)
            else:
                if mask.shape != (b, s, n) or not torch.isfinite(mask).all().item():
                    raise ValueError("invalid MSA mask")
                if not ((mask == 0) | (mask == 1)).all().item():
                    raise ValueError("mask must be binary")
                mask = mask.to(device=msa.device, dtype=torch.bool)
            z = self.norm(msa)
            a = self.left(z) * mask.unsqueeze(-1)
            c = self.right(z) * mask.unsqueeze(-1)
            pair = torch.einsum("bsic,bsjd->bijcd", a, c)
            counts = torch.einsum("bsi,bsj->bij", mask.to(msa.dtype), mask.to(msa.dtype))
            pair = pair / counts.clamp_min(1).unsqueeze(-1).unsqueeze(-1)
            out = self.output(pair.reshape(b, n, n, intermediate * intermediate))
            return out * (counts > 0).unsqueeze(-1)

    return OuterProductMean()
