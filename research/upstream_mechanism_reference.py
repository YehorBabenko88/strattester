"""Independent mathematical reference oracles for structural operators.

No import of production structural modules. Tiny tensors only; float64 reference.
These equations check adaptations, NOT original AlphaFold parameter equivalence.
"""
from __future__ import annotations
import math


def outer_product_reference(left, right, mask):
    """left/right [S,N,D]; mask [S,N]. Return [N,N,D,D], count normalized."""
    import torch
    s, n, d = left.shape
    if right.shape != (s,n,d) or mask.shape != (s,n):
        raise ValueError("shape mismatch")
    out = left.new_zeros((n,n,d,d))
    for i in range(n):
        for j in range(n):
            valid = [k for k in range(s) if bool(mask[k,i]) and bool(mask[k,j])]
            if valid:
                for k in valid:
                    for a in range(d):
                        for b in range(d):
                            out[i,j,a,b] += left[k,i,a] * right[k,j,b]
                out[i,j] /= len(valid)
    return out


def triangle_reference(left, right, mask, *, incoming):
    """left/right [N,N,D], binary mask [N,N], return [N,N,D]."""
    import torch
    n, _, d = left.shape
    if right.shape != left.shape or mask.shape != (n,n):
        raise ValueError("shape mismatch")
    out = left.new_zeros((n,n,d))
    for i in range(n):
        for j in range(n):
            if not bool(mask[i,j]):
                continue
            for k in range(n):
                if incoming:
                    if bool(mask[k,i]) and bool(mask[k,j]):
                        out[i,j] += left[k,i] * right[k,j]
                elif bool(mask[i,k]) and bool(mask[j,k]):
                    out[i,j] += left[i,k] * right[j,k]
    return out


def attention_reference(q, k, v, bias, key_mask, query_mask=None):
    """q/k/v [N,H,D], bias [H,N,N], key_mask [N], output [N,H,D]."""
    import torch
    n,h,d=q.shape
    if k.shape != q.shape or v.shape != q.shape or bias.shape != (h,n,n):
        raise ValueError("attention shape mismatch")
    out=q.new_zeros(q.shape)
    for i in range(n):
        if query_mask is not None and not bool(query_mask[i]):
            continue
        keys=[j for j in range(n) if bool(key_mask[j])]
        if not keys:
            continue
        for head in range(h):
            scores=torch.stack([(q[i,head]*k[j,head]).sum()/math.sqrt(d)+bias[head,i,j] for j in keys])
            weights=torch.softmax(scores,0)
            for w,j in zip(weights,keys):
                out[i,head] += w*v[j,head]
    return out
