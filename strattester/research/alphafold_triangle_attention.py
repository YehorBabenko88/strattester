"""Independent research adaptation of AlphaFold-style triangle attention.

Pair rows are attended along the third vertex, with pair-derived attention bias.
Not AlphaFold inference, not an exact upstream port, and not a trading model.
"""
from __future__ import annotations


def build_triangle_attention(channels: int, heads: int = 4, *, max_attention_elements: int = 2_000_000):
    if channels < 1 or heads < 1 or channels % heads or max_attention_elements < 1:
        raise ValueError("invalid attention dimensions or budget")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("optional torch dependency required") from exc

    class TriangleAttention(nn.Module):
        def __init__(self, ending: bool):
            super().__init__()
            self.ending = ending
            self.norm = nn.LayerNorm(channels)
            self.q = nn.Linear(channels, channels, bias=False)
            self.k = nn.Linear(channels, channels, bias=False)
            self.v = nn.Linear(channels, channels, bias=False)
            self.bias = nn.Linear(channels, heads, bias=False)
            self.gate = nn.Linear(channels, channels)
            self.output = nn.Linear(channels, channels)

        def forward(self, pair, mask=None):
            if pair.ndim != 4 or pair.shape[1] != pair.shape[2] or pair.shape[-1] != channels:
                raise ValueError("expected [B,N,N,C]")
            b, n, _, _ = pair.shape
            if b * heads * n ** 3 > max_attention_elements:
                raise ValueError("triangle attention budget exceeded")
            if not torch.isfinite(pair).all().item():
                raise ValueError("nonfinite pair input")
            if mask is None:
                mask = torch.ones(pair.shape[:3], device=pair.device, dtype=torch.bool)
            else:
                if mask.shape != pair.shape[:3] or not torch.isfinite(mask).all().item():
                    raise ValueError("invalid attention mask")
                if not ((mask == 0) | (mask == 1)).all().item():
                    raise ValueError("mask must be binary")
                mask = mask.to(device=pair.device, dtype=torch.bool)
            z = pair.transpose(1, 2) if self.ending else pair
            m = mask.transpose(1, 2) if self.ending else mask
            z = self.norm(z)
            d = channels // heads
            q = self.q(z).reshape(b, n, n, heads, d).permute(0, 1, 3, 2, 4)
            k = self.k(z).reshape(b, n, n, heads, d).permute(0, 1, 3, 2, 4)
            v = self.v(z).reshape(b, n, n, heads, d).permute(0, 1, 3, 2, 4)
            scores = torch.einsum("bihqd,bihkd->bihqk", q, k) * (d ** -0.5)
            # Bias from the third edge (query vertex, key vertex).
            edge_bias = self.bias(z).permute(0, 3, 1, 2)
            scores = scores + edge_bias[:, None]
            valid_keys = m[:, :, None, None, :]
            scores = scores.masked_fill(~valid_keys, torch.finfo(scores.dtype).min)
            weights = torch.softmax(scores, dim=-1)
            weights = weights * valid_keys
            weights = weights / weights.sum(dim=-1, keepdim=True).clamp_min(torch.finfo(weights.dtype).tiny)
            result = torch.einsum("bihqk,bihkd->bihqd", weights, v)
            result = result.permute(0, 1, 3, 2, 4).reshape(b, n, n, channels)
            result = self.output(result * torch.sigmoid(self.gate(z)))
            result = result * m.unsqueeze(-1)
            return result.transpose(1, 2) if self.ending else result

    return TriangleAttention(False), TriangleAttention(True)
