"""Safe-by-default broker boundary: no Python fallback or model execution."""
from .windows_native_sandbox_admission import SandboxDenied, SandboxPolicy


def launch_research_sandbox(*, policy: SandboxPolicy, executable: str, arguments=()):
    """Future native broker entry point. Intentionally denies all invocations."""
    if type(policy) is not SandboxPolicy:
        raise SandboxDenied("invalid policy type")
    policy.validate()
    if type(executable) is not str or not executable:
        raise SandboxDenied("invalid executable")
    if type(arguments) not in (tuple, list) or any(type(a) is not str for a in arguments):
        raise SandboxDenied("invalid arguments")
    raise SandboxDenied("native broker and OS enforcement not installed; no process created")
