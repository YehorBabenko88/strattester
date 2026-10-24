"""Offline experimental MSA-to-pair bridge, not a complete Evoformer.

The caller must enforce causal availability and alignment of MSA-like tracks.
This module performs no data access, model weight loading or trading.
"""
from __future__ import annotations


def build_msa_pair_bridge(msa_channels: int = 16, pair_channels: int = 32,
                          intermediate: int = 8, heads: int = 4,
                          pair_depth: int = 1, max_tokens: int = 32,
                          max_outer_elements: int = 2_000_000):
    if msa_channels < 1 or pair_channels < 1 or intermediate < 1:
        raise ValueError("invalid channel configuration")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("optional torch dependency required") from exc
    from .alphafold_outer_product import build_outer_product_mean
    from .alphafold_pair_stack import build_pair_stack

    class Bridge(nn.Module):
        def __init__(self):
            super().__init__()
            self.outer = build_outer_product_mean(
                msa_channels, pair_channels, intermediate,
                max_elements=max_outer_elements,
            )
            self.stack = build_pair_stack(
                channels=pair_channels, heads=heads,
                depth=pair_depth, max_tokens=max_tokens,
            )

        def forward(self, msa, msa_mask=None, pair=None, pair_mask=None):
            if msa.ndim != 4 or msa.shape[-1] != msa_channels:
                raise ValueError("expected [B,S,N,Cm]")
            b, _, n, _ = msa.shape
            if n < 2 or n > max_tokens:
                raise ValueError("token budget exceeded")
            if pair is not None and pair.shape != (b, n, n, pair_channels):
                raise ValueError("invalid initial pair shape")
            if pair is not None and not torch.isfinite(pair).all().item():
                raise ValueError("nonfinite initial pair")
            if pair_mask is not None:
                if pair_mask.shape != (b, n, n) or not torch.isfinite(pair_mask).all().item():
                    raise ValueError("invalid pair mask")
                if not ((pair_mask == 0) | (pair_mask == 1)).all().item():
                    raise ValueError("pair mask must be binary")
                effective_pair_mask = pair_mask.to(device=msa.device, dtype=torch.bool)
            else:
                effective_pair_mask = torch.ones((b, n, n), device=msa.device, dtype=torch.bool)
            if msa_mask is not None:
                if msa_mask.shape != (b, msa.shape[1], n):
                    raise ValueError("invalid MSA mask")
                if not torch.isfinite(msa_mask).all().item() or not ((msa_mask == 0) | (msa_mask == 1)).all().item():
                    raise ValueError("MSA mask must be finite and binary")
                available = msa_mask.to(device=msa.device, dtype=torch.bool).any(dim=1)
                effective_pair_mask = effective_pair_mask & available[:, :, None] & available[:, None, :]
            update = self.outer(msa, msa_mask)
            if pair is None:
                pair = torch.zeros_like(update)
            combined = (pair + update) * effective_pair_mask.unsqueeze(-1)
            return self.stack(combined, effective_pair_mask)

    return Bridge()
