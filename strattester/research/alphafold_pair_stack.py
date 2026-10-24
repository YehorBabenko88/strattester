"""Offline pair-stack research module, not full AlphaFold Evoformer.

Combines existing triangle operators with residual pair transition. No MSA,
outer-product mean, IPA, biological weights, DB or trading integrations.
"""
from __future__ import annotations


def build_pair_stack(channels: int = 32, heads: int = 4, depth: int = 2,
                     intermediate: int = 64, max_tokens: int = 64):
    if channels < 1 or heads < 1 or channels % heads or depth < 1 or intermediate < 1 or not 2 <= max_tokens <= 256:
        raise ValueError("invalid stack configuration")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("optional torch dependency required") from exc
    from .alphafold_triangle import build_triangle_updates
    from .alphafold_triangle_attention import build_triangle_attention

    class PairLayer(nn.Module):
        def __init__(self):
            super().__init__()
            self.mul_out, self.mul_in = build_triangle_updates(channels, intermediate)
            self.att_start, self.att_end = build_triangle_attention(channels, heads)
            self.transition_norm = nn.LayerNorm(channels)
            self.transition = nn.Sequential(
                nn.Linear(channels, 4 * channels), nn.ReLU(),
                nn.Linear(4 * channels, channels)
            )

        def forward(self, pair, mask):
            for module in (self.mul_out, self.mul_in, self.att_start, self.att_end):
                pair = (pair + module(pair, mask)) * mask.unsqueeze(-1)
            pair = (pair + self.transition(self.transition_norm(pair))) * mask.unsqueeze(-1)
            return pair

    class PairStack(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = nn.ModuleList(PairLayer() for _ in range(depth))

        def forward(self, pair, mask=None):
            if pair.ndim != 4 or pair.shape[1] != pair.shape[2] or pair.shape[-1] != channels:
                raise ValueError("expected [B,N,N,C]")
            b, n, _, _ = pair.shape
            if n < 2 or n > max_tokens:
                raise ValueError("token budget exceeded")
            if not torch.isfinite(pair).all().item():
                raise ValueError("nonfinite pair features")
            if mask is None:
                mask = torch.ones((b, n, n), device=pair.device, dtype=torch.bool)
            else:
                if mask.shape != (b, n, n) or not torch.isfinite(mask).all().item():
                    raise ValueError("invalid pair mask")
                if not ((mask == 0) | (mask == 1)).all().item():
                    raise ValueError("mask must be binary")
                mask = mask.to(device=pair.device, dtype=torch.bool)
            pair = pair * mask.unsqueeze(-1)
            for layer in self.layers:
                pair = layer(pair, mask)
            return pair

    return PairStack()
