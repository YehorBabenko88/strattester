"""Research-only AlphaFold-style triangular multiplicative updates.

Mathematical operator adaptation, NOT the original AlphaFold inference pipeline.
No biological weights, atom heads, database access, or trading execution.
"""
from __future__ import annotations


def build_triangle_updates(channels: int, intermediate: int = 128):
    if channels < 1 or intermediate < 1:
        raise ValueError("channels and intermediate must be positive")
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
            if not torch.isfinite(pair).all():
                raise ValueError("nonfinite pair input")
            if mask is not None:
                if mask.shape != pair.shape[:3]:
                    raise ValueError("mask must be [B,N,N]")
                mask = mask.to(device=pair.device, dtype=pair.dtype).unsqueeze(-1)
            z = self.norm(pair)
            a = self.left(z) * torch.sigmoid(self.left_gate(z))
            b = self.right(z) * torch.sigmoid(self.right_gate(z))
            if mask is not None:
                a, b = a * mask, b * mask
            if self.incoming:
                mixed = torch.einsum("bkih,bkjh->bijh", a, b)
            else:
                mixed = torch.einsum("bikh,bjkh->bijh", a, b)
            out = torch.sigmoid(self.output_gate(z)) * self.output(self.center_norm(mixed))
            return out if mask is None else out * mask

    return TriangleMultiplication(False), TriangleMultiplication(True)
