"""Bound authenticated funding dataset and authenticated producer coverage.

Both signatures must verify against externally pinned keys. Producer assertions
do not establish independently observed completeness or real-market OOS.
"""
from research.alphafold_training.authenticated_funding import verify_funding
from research.alphafold_training.funding_coverage_manifest import verify_coverage_manifest
from research.alphafold_training.authenticated_reconciliation import reconcile_authenticated

def reconcile_with_manifest(trades, records, manifest, *, funding_key, funding_mac,
                            manifest_key, manifest_mac, fee_bps=0., slippage_bps=0.):
    if type(manifest) is not dict:
        raise ValueError("coverage manifest required")
    rows = list(records)
    trades = list(trades)
    auth = verify_funding(
        rows, producer=manifest.get("producer"), epoch=manifest.get("epoch"),
        dataset_version=manifest.get("dataset_version"),
        trusted_key=funding_key, expected_mac=funding_mac)
    coverage = verify_coverage_manifest(
        manifest, trusted_key=manifest_key, expected_mac=manifest_mac,
        funding_sha256=auth["sha256"])
    if not trades:
        raise ValueError("empty trades")
    if any(t.instrument not in coverage["instruments"]
           or t.start_ns < coverage["coverage_start_ns"]
           or t.end_ns > coverage["coverage_end_ns"] for t in trades):
        raise ValueError("trade outside authenticated producer coverage")
    result = reconcile_authenticated(
        trades, rows, producer=manifest["producer"], epoch=manifest["epoch"],
        dataset_version=manifest["dataset_version"],
        trusted_key=funding_key, expected_mac=funding_mac,
        coverage_start_ns=coverage["coverage_start_ns"],
        coverage_end_ns=coverage["coverage_end_ns"],
        fee_bps=fee_bps, slippage_bps=slippage_bps)
    result["coverage_manifest_sha256"] = coverage["manifest_sha256"]
    result["coverage_producer_assertion_authenticated"] = True
    result["coverage_completeness_verified"] = False
    result["real_oos_authorized"] = False
    return result
