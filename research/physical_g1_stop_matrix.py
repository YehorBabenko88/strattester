"""Independent fail-closed STOP matrix; never authorizes physical execution."""
from __future__ import annotations

REQUIRED = frozenset({
    "exact_head", "source_tree", "seven_gates", "native_job",
    "artifact_sha256", "junit_required_ids", "owner_signature",
    "owner_plan_nonce", "windows_acl", "token_and_job", "handle_confinement",
    "reparse_race", "network_ipv4_ipv6_dns_udp_loopback",
    "descendant_isolation", "resource_limits", "cancel_cleanup",
    "disposable_vm_adversarial", "grid_snapshot", "real_oos",
})


def evaluate_physical_g1(evidence: object) -> dict:
    if type(evidence) is not dict:
        return {"status": "BLOCKED", "stop": ["invalid_evidence"]}
    missing = sorted(REQUIRED - set(evidence))
    extra = sorted(set(evidence) - REQUIRED)
    unverified = sorted(k for k in REQUIRED if evidence.get(k) != "INDEPENDENT_VERIFIED")
    stop = sorted(set(missing + extra + unverified))
    # An all-green self-asserted dictionary is not independent authorization.
    if not stop:
        stop = ["external_authority_and_signed_plan_not_verified_by_this_module"]
    return {"status": "BLOCKED", "stop": stop, "physical_g1_authorized": False}
