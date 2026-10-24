"""Fail-closed Windows native sandbox admission contract.

This module is intentionally NOT a process launcher. No execution is permitted
until a native, independently verified backend exists. Never use subprocess as
a fallback.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import PureWindowsPath


class SandboxDenied(RuntimeError):
    pass


class Capability(str, Enum):
    RESTRICTED_PRIMARY_TOKEN = "restricted_primary_token"
    PRIVILEGES_REMOVED = "privileges_removed"
    CREATE_SUSPENDED = "create_suspended"
    JOB_ASSIGNED_BEFORE_RESUME = "job_assigned_before_resume"
    KILL_ON_CLOSE = "kill_on_close"
    PROCESS_TREE_LIMIT = "process_tree_limit"
    CPU_LIMIT = "cpu_limit"
    MEMORY_LIMIT = "memory_limit"
    WALL_CLOCK_LIMIT = "wall_clock_limit"
    OUTPUT_BYTE_LIMIT = "output_byte_limit"
    HANDLE_INHERITANCE_DENIED = "handle_inheritance_denied"
    FILESYSTEM_HANDLE_CONFINEMENT = "filesystem_handle_confinement"
    REPARSE_ADS_DEVICE_DENIED = "reparse_ads_device_denied"
    IPV4_IPV6_DNS_LOOPBACK_EGRESS_DENIED = "ipv4_ipv6_dns_loopback_egress_denied"
    CHILD_NETWORK_POLICY = "child_network_policy"
    POLICY_EFFECTIVENESS_ATTESTED = "policy_effectiveness_attested"


@dataclass(frozen=True)
class SandboxPolicy:
    cpu_percent: int
    memory_bytes: int
    timeout_seconds: int
    max_output_bytes: int
    max_processes: int = 1

    def validate(self):
        values = (self.cpu_percent, self.memory_bytes, self.timeout_seconds,
                  self.max_output_bytes, self.max_processes)
        if any(type(v) is not int or v <= 0 for v in values):
            raise SandboxDenied("invalid resource policy")
        if self.cpu_percent > 100 or self.max_processes != 1:
            raise SandboxDenied("unsupported process or CPU policy")


def reject_unsafe_windows_path(path: str) -> str:
    """Lexical prefilter only; native handle-based check is still mandatory."""
    if type(path) is not str or not path:
        raise SandboxDenied("invalid path")
    if "/" in path:
        raise SandboxDenied("mixed or forward separators")
    p = path
    if "\x00" in p or any(ord(c) < 32 for c in p):
        raise SandboxDenied("control character in path")
    if len(p) < 4 or (p[1] != ":" or p[2] != "\\") or not p[0].isascii() or not p[0].isalpha():
        raise SandboxDenied("noncanonical drive path")
    if (not PureWindowsPath(p).is_absolute()
            or p.startswith("\\\\")
            or p.startswith("\\\\?\\")
            or p.startswith("\\\\.\\")
            or ":" in p[2:]
            or any(part in ("..", ".") for part in p[3:].split("\\"))
            or any(not part for part in p[3:].split("\\"))
            or any(part.rstrip(" .") != part for part in p[3:].split("\\"))
            or any(part.split(".")[0].upper() in
                   ({"CON", "PRN", "AUX", "NUL"} |
                    {"COM" + str(i) for i in range(1, 10)} |
                    {"LPT" + str(i) for i in range(1, 10)})
                   for part in p[3:].split("\\"))):
        raise SandboxDenied("unsafe Windows path")
    return p


def require_verified_capabilities(policy: SandboxPolicy, attested: dict):
    if type(policy) is not SandboxPolicy:
        raise SandboxDenied("invalid policy type")
    policy.validate()
    if type(attested) is not dict or set(attested) != {c.value for c in Capability}:
        raise SandboxDenied("missing or unexpected capability evidence")
    if any(type(v) is not bool or v is not True for v in attested.values()):
        raise SandboxDenied("sandbox capability not independently verified")
    # Deliberately deny even a self-asserted complete dictionary: no native
    # verifier, cryptographic provenance or OS enforcement is integrated yet.
    raise SandboxDenied("native sandbox verifier unavailable; execution forbidden")
