"""Offline QA probes for native sandbox evidence (never launches a child)."""
import hashlib
import os
import stat
from pathlib import Path

from .windows_native_sandbox_admission import SandboxDenied


REQUIRED_KEYS = frozenset({
    "schema", "target_sha", "policy_sha256", "binary_sha256",
    "vm_snapshot_id", "os_build", "run_id", "status",
    "native_enforcement", "independent_verifier",
})


def verify_disposable_vm_receipt(receipt, *, expected_target_sha):
    """Validate evidence shape only. Does not authorize execution or G1."""
    if type(receipt) is not dict or set(receipt) != REQUIRED_KEYS:
        raise SandboxDenied("incomplete or extra receipt fields")
    if type(receipt["schema"]) is not int or receipt["schema"] != 1 or receipt["target_sha"] != expected_target_sha:
        raise SandboxDenied("stale receipt")
    for key in ("target_sha", "policy_sha256", "binary_sha256"):
        value = receipt[key]
        size = 40 if key == "target_sha" else 64
        if type(value) is not str or len(value) != size or any(c not in "0123456789abcdef" for c in value):
            raise SandboxDenied("invalid digest")
    for key in ("vm_snapshot_id", "os_build", "run_id"):
        if type(receipt[key]) is not str or not receipt[key] or len(receipt[key]) > 256:
            raise SandboxDenied("invalid receipt identity")
    if receipt["status"] != "BLOCKED":
        raise SandboxDenied("unsigned self-attested PASS is not evidence")
    if receipt["native_enforcement"] is not False or receipt["independent_verifier"] is not False:
        raise SandboxDenied("unexpected unverified capability")
    return "BLOCKED"


def hash_static_evidence_file(path, *, max_bytes=1024 * 1024):
    """Bounded hash for a disposable static evidence file, not a live DB."""
    path = Path(path)
    if type(max_bytes) is not int or max_bytes <= 0 or path.is_symlink():
        raise SandboxDenied("unsafe evidence file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SandboxDenied("evidence file open refused") from exc
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise SandboxDenied("not a regular evidence file")
        size = 0
        while chunk := stream.read(min(65536, max_bytes - size + 1)):
            size += len(chunk)
            if size > max_bytes:
                raise SandboxDenied("oversized evidence")
            digest.update(chunk)
    return digest.hexdigest()
