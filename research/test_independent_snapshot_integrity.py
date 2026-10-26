import hashlib
import pytest
from research.independent_snapshot_integrity import verify_snapshot_bytes

def test_exact_snapshot_digest():
    payload = b"immutable snapshot\\n" + bytes(range(256))
    digest = hashlib.sha256(payload).hexdigest()
    assert verify_snapshot_bytes(payload, digest)
    with pytest.raises(ValueError, match="mismatch"):
        verify_snapshot_bytes(payload + b"!", digest)

def test_snapshot_budget_and_malformed_digest():
    payload = b"12345"
    digest = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError, match="oversized"):
        verify_snapshot_bytes(payload, digest, max_bytes=4)
    with pytest.raises(ValueError, match="expected"):
        verify_snapshot_bytes(payload, "not-a-digest")
    with pytest.raises(ValueError, match="empty"):
        verify_snapshot_bytes(b"", hashlib.sha256(b"").hexdigest())
