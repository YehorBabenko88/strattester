"""Bounded, fail-closed SHA256 verification for immutable research artifacts.

Only regular non-symlink files are supported. Do not use this verifier to
hash a live SQLite WAL database or PostgreSQL data directory: those require
a transactionally consistent exported artifact first.
"""
import hashlib
from pathlib import Path


class ArtifactVerificationError(ValueError):
    pass


def verify_immutable_artifact(path: Path, expected_sha256: str, *, max_bytes: int) -> int:
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ArtifactVerificationError("Invalid SHA256")
    if path.is_symlink() or not path.is_file():
        raise ArtifactVerificationError("Not a regular non-symlink artifact")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(min(1024 * 1024, max_bytes - size + 1)):
            size += len(chunk)
            if size > max_bytes:
                raise ArtifactVerificationError("Artifact exceeds byte limit")
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ArtifactVerificationError("Artifact SHA256 mismatch")
    return size
