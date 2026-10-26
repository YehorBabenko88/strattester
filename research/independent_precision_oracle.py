"""Independent float32/float64 numerical tolerance policy."""
import math
import struct

def float32(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("nonfinite value")
    try:
        result = struct.unpack('!f',struct.pack('!f',value))[0]
    except OverflowError as exc:
        raise ValueError("float32 overflow") from exc
    if not math.isfinite(result):
        raise ValueError("float32 overflow")
    return result

def assert_precision_close(reference, observed, *, dtype='float64'):
    if dtype not in ('float32','float64') or not all(math.isfinite(float(x)) for x in (reference,observed)):
        raise ValueError("invalid comparison")
    atol,rtol = (1e-5,1e-5) if dtype=='float32' else (1e-12,1e-12)
    if not math.isclose(float(reference),float(observed),abs_tol=atol,rel_tol=rtol):
        raise ValueError("precision tolerance exceeded")
    return True
