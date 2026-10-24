"""Fail-closed pytest gate for mandatory AlphaFold CPU operator tests.

Run as: python scripts/alphafold_cpu_gate.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

FILES = (
    "tests/research/test_alphafold_triangle.py",
    "tests/research/test_alphafold_triangle_reference.py",
    "tests/research/test_alphafold_triangle_attention.py",
    "tests/research/test_alphafold_triangle_attention_oracle.py",
    "tests/research/test_alphafold_pair_stack.py",
    "tests/research/test_alphafold_pair_stack_budget.py",
    "tests/research/test_alphafold_outer_product.py",
    "tests/research/test_alphafold_msa_pair_bridge.py",
    "tests/research/test_alphafold_msa_attention.py",
)
MIN_EXECUTED = 18


def main() -> int:
    try:
        import torch
    except ImportError:
        print("BLOCKED: torch unavailable", file=sys.stderr)
        return 2
    if torch.cuda.is_available():
        print("BLOCKED: expected CPU-only torch", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="alphafold-cpu-gate-") as tmp:
        report = Path(tmp) / "pytest.json"
        args = [
            sys.executable, "-m", "pytest", "-q", "--strict-markers",
            "-p", "no:cacheprovider", "-o", "addopts=",
            "--json-report", f"--json-report-file={report}",
            "-k", "not gpu and not cuda", *FILES,
        ]
        completed = subprocess.run(args, check=False, timeout=900)
        if completed.returncode != 0 or not report.is_file():
            print("BLOCKED: pytest failed or missing report", file=sys.stderr)
            return 1
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
            summary = payload["summary"]
            passed = int(summary.get("passed", 0))
            failed = int(summary.get("failed", 0))
            errors = int(summary.get("error", 0))
            skipped = int(summary.get("skipped", 0))
            xfailed = int(summary.get("xfailed", 0))
            xpassed = int(summary.get("xpassed", 0))
            collected = int(summary["total"])
            deselected = int(summary.get("deselected", 0))
            tests = payload["tests"]
            executed_files = {str(item["nodeid"]).split("::", 1)[0] for item in tests
                              if item.get("outcome") == "passed"}
        except (OSError, ValueError, KeyError, TypeError):
            print("BLOCKED: invalid pytest report", file=sys.stderr)
            return 1
        if (passed < MIN_EXECUTED or failed or errors or skipped or xfailed or xpassed
                or collected != passed or deselected < 0
                or not set(FILES).issubset(executed_files)):
            print(f"BLOCKED: test accounting total={collected} pass={passed} "
                  f"fail={failed} error={errors} skip={skipped} "
                  f"xfail={xfailed} xpass={xpassed}", file=sys.stderr)
            return 1
        print(f"PASS: {passed} mandatory CPU structural tests; no skips")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
