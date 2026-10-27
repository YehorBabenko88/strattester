"""Independent point-in-time source snapshot byte integrity oracle.

Metadata digests alone do not prove payload integrity. This oracle binds exact
snapshot bytes to an externally supplied manifest digest without parsing data.
"""
import hashlib
import hmac

def verify_snapshot_bytes(payload, expected_sha256, *, max_bytes=64*1024*1024):
    if not isinstance(payload, bytes) or type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("invalid snapshot input or budget")
    if len(payload) == 0 or len(payload) > max_bytes:
        raise ValueError("empty or oversized snapshot")
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_sha256)):
        raise ValueError("invalid expected snapshot SHA256")
    actual = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual, expected_sha256):
        raise ValueError("snapshot digest mismatch")
    return True
