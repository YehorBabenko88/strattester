"""Fail-closed structural pytest report attestation (offline, standard library)."""
from __future__ import annotations
import json
import sys
from pathlib import Path

REQUIRED_FILES = {
    "test_cycle3_structural_invariants.py",
    "test_cycle3_cpu_contract.py",
    "test_cycle3_operator_connectivity.py",
    "test_cycle3_forecast_contract.py",
    "test_cycle3_resource_admission.py",
    "test_cycle3_gradient_oracle.py",
    "test_cycle3_checkpoint_readiness.py",
}
EXPECTED = 38


def verify(path: Path) -> None:
    report = json.loads(path.read_text(encoding="utf-8"))
    summary = report["summary"]
    tests = report["tests"]
    if type(tests) is not list or len(tests) != EXPECTED:
        raise ValueError("missing, duplicated or unexpected test count")
    if summary.get("passed") != EXPECTED or summary.get("total") != EXPECTED:
        raise ValueError("incorrect test accounting")
    if any(summary.get(key, 0) != 0 for key in
           ("failed", "error", "skipped", "xfailed", "xpassed", "deselected")):
        raise ValueError("unaccepted test outcome")
    nodeids = []
    for test in tests:
        if test.get("outcome") != "passed" or type(test.get("nodeid")) is not str:
            raise ValueError("non-PASS test node")
        nodeids.append(test["nodeid"])
    if len(set(nodeids)) != EXPECTED:
        raise ValueError("duplicate node identity")
    files = {node.split("::", 1)[0].replace("\\", "/").rsplit("/", 1)[-1] for node in nodeids}
    if files != REQUIRED_FILES:
        raise ValueError(f"test file coverage mismatch: {sorted(files)}")


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise ValueError("exactly one report path required")
        verify(Path(sys.argv[1]))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print("PASS: 38 unique test nodes, seven required files, no skipped/failed outcomes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
