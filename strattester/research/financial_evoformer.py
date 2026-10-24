"""Experimental trainable pair-attention trunk inspired by AlphaFold Evoformer.

Independent implementation, not original AlphaFold code or weights.
Requires optional torch; never imports torch into the default research path.
"""
from __future__ import annotations


def build_financial_model(hidden: int = 32, heads: int = 4):
    if hidden < 4 or heads < 1 or hidden % heads:
        raise ValueError("hidden must be >=4 and divisible by heads")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("optional PyTorch installation required") from exc

    class PairBlock(nn.Module):
        def __init__(self):
            super().__init__()
            self.single = nn.Linear(3, hidden)
            self.pair = nn.Linear(1, hidden)
            self.attention = nn.MultiheadAttention(hidden, heads, batch_first=True)
            self.triangle_left = nn.Linear(hidden, hidden)
            self.triangle_right = nn.Linear(hidden, hidden)
            self.norm = nn.LayerNorm(hidden)
            self.head = nn.Sequential(nn.Linear(hidden * 2, hidden),
                                      nn.GELU(), nn.Linear(hidden, 2))

        def forward(self, single, pair):
            # single: [B,N,3]; pair: [B,N,N], all inputs causal at forecast origin.
            if single.ndim != 3 or single.shape[-1] != 3:
                raise ValueError("single must have shape [B,N,3]")
            b, n, _ = single.shape
            if n < 2 or n > 1024 or pair.shape != (b, n, n):
                raise ValueError("pair shape mismatch or unsupported length")
            if not torch.isfinite(single).all() or not torch.isfinite(pair).all():
                raise ValueError("nonfinite inputs")
            x = self.single(single)
            p = self.pair(pair.unsqueeze(-1))
            # Pair mixing across the intermediate index is a triangle-like
            # update, not a faithful implementation of AlphaFold's triangle block.
            left = self.triangle_left(p)
            right = self.triangle_right(p)
            p = p + torch.einsum("bikh,bkjh->bijh", left, right) / n
            bias = p.mean(dim=2)
            x, _ = self.attention(x + bias, x + bias, x, need_weights=False)
            x = self.norm(x + bias)
            pooled = torch.cat((x[:, -1], p[:, -1].mean(dim=1)), dim=-1)
            # Predicted future log-return and log-volatility (not price directly).
            return self.head(pooled)

    return PairBlock()
