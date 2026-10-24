import hashlib
import pytest

from strattester.alphafold_artifact_verify import (
    ArtifactVerificationError, verify_immutable_artifact,
)


def test_valid_artifact(tmp_path):
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"known dataset")
    expected = hashlib.sha256(b"known dataset").hexdigest()
    assert verify_immutable_artifact(path, expected, max_bytes=100) == 13


def test_tampered_artifact_rejected(tmp_path):
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"tampered")
    with pytest.raises(ArtifactVerificationError, match="mismatch"):
        verify_immutable_artifact(path, "0" * 64, max_bytes=100)


def test_oversized_artifact_rejected(tmp_path):
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"x" * 101)
    with pytest.raises(ArtifactVerificationError, match="byte limit"):
        verify_immutable_artifact(path, "0" * 64, max_bytes=100)


def test_symlink_artifact_rejected(tmp_path):
    path = tmp_path / "real.bin"
    path.write_bytes(b"abc")
    link = tmp_path / "alias.bin"
    try:
        link.symlink_to(path)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(ArtifactVerificationError, match="non-symlink"):
        verify_immutable_artifact(link, "0" * 64, max_bytes=100)
