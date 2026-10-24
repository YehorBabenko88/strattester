import pytest
from strattester.research.windows_native_launcher import launch_research_sandbox
from strattester.research.windows_native_sandbox_admission import SandboxDenied, SandboxPolicy


def test_no_native_broker_means_no_execution(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("subprocess fallback"))
    policy = SandboxPolicy(cpu_percent=10, memory_bytes=64 * 1024 * 1024,
                           timeout_seconds=1, max_output_bytes=128)
    with pytest.raises(SandboxDenied, match="no process created"):
        launch_research_sandbox(policy=policy, executable=r"C:\safe\model.exe")


def test_launcher_rejects_fake_policy_object():
    class FakePolicy:
        def validate(self):
            pytest.fail("untrusted validate must not run")
    with pytest.raises(SandboxDenied, match="invalid policy type"):
        launch_research_sandbox(policy=FakePolicy(), executable=r"C:\safe\model.exe")


def test_launcher_rejects_bad_args():
    policy = SandboxPolicy(cpu_percent=10, memory_bytes=64 * 1024 * 1024,
                           timeout_seconds=1, max_output_bytes=128)
    with pytest.raises(SandboxDenied):
        launch_research_sandbox(policy=policy, executable=r"C:\safe\model.exe",
                                arguments=[True])
