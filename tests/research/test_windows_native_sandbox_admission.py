import pytest
from strattester.research.windows_native_sandbox_admission import (
    SandboxDenied, SandboxPolicy, Capability, reject_unsafe_windows_path,
    require_verified_capabilities,
)


def policy():
    return SandboxPolicy(cpu_percent=20, memory_bytes=256 * 1024 * 1024,
                         timeout_seconds=10, max_output_bytes=4096)


@pytest.mark.parametrize("path", [
    "../model.json", r"\\server\share\model.json",
    r"\\?\C:\model.json", r"\\.\PhysicalDrive0",
    r"C:\safe\..\secret", r"C:\safe\file:stream",
    r"C:\safe\NUL", "C:\\safe\\file.",
    r"C:\safe\COM9.txt", r"C:\safe\LPT8",
    r"C:\safe\\double", r"C:\safe\.\model", r"C:\safe\..\model",
    "C:\\safe\\bad\\x00name", "C:\\safe\\bad\\x01name",
])
def test_unsafe_paths_denied(path):
    with pytest.raises(SandboxDenied):
        reject_unsafe_windows_path(path)


@pytest.mark.parametrize("kwargs", [
    {"cpu_percent": 0}, {"cpu_percent": 101}, {"max_processes": 2},
    {"memory_bytes": True}, {"timeout_seconds": -1},
])
def test_invalid_policy_denied(kwargs):
    base = vars(policy()).copy()
    base.update(kwargs)
    with pytest.raises(SandboxDenied):
        SandboxPolicy(**base).validate()


def test_canonical_path_prefilter_only():
    assert reject_unsafe_windows_path(r"C:\safe\model.json") == r"C:\safe\model.json"


def test_no_capability_evidence_denied():
    with pytest.raises(SandboxDenied):
        require_verified_capabilities(policy(), {})


def test_missing_single_capability_denied():
    evidence = {c.value: True for c in Capability}
    evidence.pop(Capability.CHILD_NETWORK_POLICY.value)
    with pytest.raises(SandboxDenied):
        require_verified_capabilities(policy(), evidence)


def test_self_attested_all_true_still_denied():
    evidence = {c.value: True for c in Capability}
    with pytest.raises(SandboxDenied, match="native sandbox verifier unavailable"):
        require_verified_capabilities(policy(), evidence)
