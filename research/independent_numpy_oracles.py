"""NumPy independent matrix oracles; optional dependency and never GPU."""
import numpy as np

def masked_attention_reference(q, k, v, mask):
    q, k, v = (np.asarray(x, dtype=np.float64) for x in (q, k, v))
    mask = np.asarray(mask)
    if q.ndim != 2 or k.ndim != 2 or v.ndim != 2 or q.shape[1] != k.shape[1] or k.shape[0] != v.shape[0] or mask.shape != (q.shape[0], k.shape[0]) or mask.dtype != np.bool_:
        raise ValueError("invalid attention shape or mask")
    if not all(np.isfinite(x).all() for x in (q, k, v)):
        raise ValueError("nonfinite attention inputs")
    logits = q @ k.T / np.sqrt(q.shape[1])
    out = np.zeros((q.shape[0], v.shape[1]), dtype=np.float64)
    for i in range(q.shape[0]):
        allowed = mask[i]
        if not allowed.any():
            continue
        z = logits[i, allowed]
        weights = np.exp(z - z.max())
        weights /= weights.sum()
        out[i] = weights @ v[allowed]
    return out

def triangle_outgoing_reference(pair, mask):
    pair = np.asarray(pair, dtype=np.float64)
    mask = np.asarray(mask)
    if pair.ndim != 3 or pair.shape[0] != pair.shape[1] or mask.shape != pair.shape[:2] or mask.dtype != np.bool_:
        raise ValueError("invalid triangle dimensions")
    if not np.isfinite(pair).all():
        raise ValueError("nonfinite triangle")
    n, _, channels = pair.shape
    out = np.zeros_like(pair)
    for i in range(n):
        for j in range(n):
            if not mask[i, j]:
                continue
            for k in range(n):
                if mask[i, k] and mask[j, k]:
                    out[i, j] += pair[i, k] * pair[j, k]
    return out
