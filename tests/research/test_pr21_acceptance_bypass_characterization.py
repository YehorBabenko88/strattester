"""Adversarial proof of current acceptance API weakness, target PR21 SHA.

These tests intentionally document *observed* insecure behavior. Once fixed,
replace assertions with rejection expectations and pin the required manifest.
"""
from strattester.research.financial_acceptance import aggregate


SHA = "67301726d250973602b964adabdb9eb8d50d0f13"


def _forged_report():
    return {
        "schema": 1, "sha": SHA, "gate": "cpu", "status": "PASS",
        "passed": 1, "failed": 0, "errors": 0, "skipped": 0,
        "xfailed": 0, "xpassed": 0, "deselected": 0,
        "collected": 1, "nodeids": ["forged.py::test_arbitrary"],
        "exit_code": 0,
    }


def test_aggregate_accepts_self_attested_arbitrary_required_id():
    result = aggregate({"cpu": _forged_report()}, SHA, {"cpu"},
                       external={"grid_coherent_snapshot": "PASS"})
    assert result["status"] == "PASS", result


def test_aggregate_accepts_missing_external_requirements():
    result = aggregate({"cpu": _forged_report()}, SHA, {"cpu"}, external={})
    assert result["status"] == "PASS", result
