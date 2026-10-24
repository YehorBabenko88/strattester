"""Research-only gated triangle multiplication (AlphaFold-style operator).

Not AlphaFold inference. No biological weights, DB access or trading side effects.
"""
from __future__ import annotations


def build_triangle_updates(channels: int, intermediate: int = 128, *, max_pair_elements: int = 2_000_000):
    if channels < 1 or intermediate < 1 or max_pair_elements < 1:
        raise ValueError("invalid operator dimensions or budget")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("optional torch dependency required") from exc

    class TriangleMultiplication(nn.Module):
        def __init__(self, incoming: bool):
            super().__init__()
            self.incoming = incoming
            self.norm = nn.LayerNorm(channels)
            self.left = nn.Linear(channels, intermediate)
            self.right = nn.Linear(channels, intermediate)
            self.left_gate = nn.Linear(channels, intermediate)
            self.right_gate = nn.Linear(channels, intermediate)
            self.center_norm = nn.LayerNorm(intermediate)
            self.output = nn.Linear(intermediate, channels)
            self.output_gate = nn.Linear(channels, channels)

        def forward(self, pair, mask=None):
            if pair.ndim != 4 or pair.shape[1] != pair.shape[2] or pair.shape[-1] != channels:
                raise ValueError("expected pair [B,N,N,C]")
            batch, n, _, _ = pair.shape
            # Preflight budget covers the largest expanded intermediates, not
            # just the input tensor. This is an element limit, not a GPU OOM guarantee.
            if batch * n * n * max(channels, intermediate) > max_pair_elements:
                raise ValueError("pair intermediate budget exceeded")
            if not torch.isfinite(pair).all().item():
                raise ValueError("nonfinite pair input")
            if mask is not None:
                if mask.shape != pair.shape[:3]:
                    raise ValueError("mask must be [B,N,N]")
                if not torch.isfinite(mask).all().item() or not ((mask == 0) | (mask == 1)).all().item():
                    raise ValueError("mask must be finite and binary")
                mask = mask.to(device=pair.device, dtype=pair.dtype).unsqueeze(-1)
            z = self.norm(pair)
            a = self.left(z) * torch.sigmoid(self.left_gate(z))
            b = self.right(z) * torch.sigmoid(self.right_gate(z))
            if mask is not None:
                a, b = a * mask, b * mask
            if self.incoming:
                # Pinned AlphaFold config: left[k,j] * right[k,i]. The
                # incoming algorithm swaps the left/right projection roles.
                mixed = torch.einsum("bkjh,bkih->bijh", a, b)
            else:
                mixed = torch.einsum("bikh,bjkh->bijh", a, b)
            out = torch.sigmoid(self.output_gate(z)) * self.output(self.center_norm(mixed))
            return out if mask is None else out * mask

    return TriangleMultiplication(False), TriangleMultiplication(True)
