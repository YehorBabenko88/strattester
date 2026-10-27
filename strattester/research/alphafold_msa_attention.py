"""Offline MSA row attention with pair-derived bias (research adaptation).

Tokens attend within each aligned track, not across future timesteps.
Caller must enforce causal masks and time-alignment. Not original AlphaFold.
"""
from __future__ import annotations


def build_msa_row_attention(msa_channels: int, pair_channels: int,
                            heads: int = 4, *, max_attention_elements: int = 2_000_000):
    if min(msa_channels, pair_channels, heads, max_attention_elements) < 1 or msa_channels % heads:
        raise ValueError("invalid attention dimensions")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("optional torch dependency required") from exc

    class RowAttention(nn.Module):
        def __init__(self):
            super().__init__()
            self.msa_norm = nn.LayerNorm(msa_channels)
            self.pair_norm = nn.LayerNorm(pair_channels)
            self.qkv = nn.Linear(msa_channels, 3 * msa_channels, bias=False)
            self.pair_bias = nn.Linear(pair_channels, heads, bias=False)
            self.gate = nn.Linear(msa_channels, msa_channels)
            self.output = nn.Linear(msa_channels, msa_channels)

        def forward(self, msa, pair, msa_mask=None, causal=False):
            if msa.ndim != 4 or pair.ndim != 4:
                raise ValueError("expected MSA and pair tensors")
            b, s, n, c = msa.shape
            if c != msa_channels or pair.shape != (b, n, n, pair_channels):
                raise ValueError("incompatible MSA/pair shapes")
            if n < 2 or b * s * heads * n * n > max_attention_elements:
                raise ValueError("attention budget exceeded")
            if not torch.isfinite(msa).all().item() or not torch.isfinite(pair).all().item():
                raise ValueError("nonfinite input")
            if msa_mask is None:
                mask = torch.ones((b, s, n), device=msa.device, dtype=torch.bool)
            else:
                if msa_mask.shape != (b, s, n) or not torch.isfinite(msa_mask).all().item():
                    raise ValueError("invalid MSA mask")
                if not ((msa_mask == 0) | (msa_mask == 1)).all().item():
                    raise ValueError("MSA mask must be binary")
                mask = msa_mask.to(device=msa.device, dtype=torch.bool)
            z = self.msa_norm(msa)
            q, k, v = self.qkv(z).reshape(b, s, n, 3, heads, c // heads).unbind(dim=3)
            scores = torch.einsum("bsihd,bsjhd->bshij", q, k) * ((c // heads) ** -0.5)
            bias = self.pair_bias(self.pair_norm(pair)).permute(0, 3, 1, 2)
            scores = scores + bias[:, None]
            allowed = mask[:, :, None, None, :].expand(b, s, heads, n, n)
            if causal:
                allowed = allowed & torch.ones((n, n), device=msa.device, dtype=torch.bool).tril()
            scores = scores.masked_fill(~allowed, torch.finfo(scores.dtype).min)
            weights = torch.softmax(scores, dim=-1) * allowed
            # 1e-9 rounds to zero in float16: an empty key set then divides
            # zero by zero. Keep the denominator representable in every dtype.
            weights = weights / weights.sum(dim=-1, keepdim=True).clamp_min(torch.finfo(weights.dtype).tiny)
            attended = torch.einsum("bshij,bsjhd->bsihd", weights, v).reshape(b, s, n, c)
            result = self.output(attended * torch.sigmoid(self.gate(z)))
            return result * mask.unsqueeze(-1)

    return RowAttention()
