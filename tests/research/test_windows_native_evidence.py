import hashlib
import pytest
from strattester.research.windows_native_evidence import (
    verify_disposable_vm_receipt, hash_static_evidence_file,
)
from strattester.research.windows_native_sandbox_admission import SandboxDenied

SHA = "67301726d250973602b964adabdb9eb8d50d0f13"


def receipt():
    return dict(schema=1, target_sha=SHA, policy_sha256="a"*64,
                binary_sha256="b"*64, vm_snapshot_id="disposable-vm-01",
                os_build="test-only", run_id="offline-01", status="BLOCKED",
                native_enforcement=False, independent_verifier=False)


def test_unsigned_blocked_receipt_never_authorizes():
    assert verify_disposable_vm_receipt(receipt(), expected_target_sha=SHA) == "BLOCKED"


@pytest.mark.parametrize("change", [
    {"status": "PASS"}, {"target_sha": "c"*40}, {"native_enforcement": True},
    {"independent_verifier": True}, {"policy_sha256": "bad"},
    {"schema": True}, {"run_id": ""},
])
def test_forged_receipts_denied(change):
    bad = receipt()
    bad.update(change)
    with pytest.raises(SandboxDenied):
        verify_disposable_vm_receipt(bad, expected_target_sha=SHA)


def test_symlink_evidence_denied(tmp_path):
    target = tmp_path / "target.txt"
    target.write_bytes(b"fixture")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(SandboxDenied):
        hash_static_evidence_file(link)


def test_evidence_file_hash_and_size(tmp_path):
    path = tmp_path / "receipt.txt"
    path.write_bytes(b"fixture")
    assert hash_static_evidence_file(path) == hashlib.sha256(b"fixture").hexdigest()
    with pytest.raises(SandboxDenied):
        hash_static_evidence_file(path, max_bytes=2)
