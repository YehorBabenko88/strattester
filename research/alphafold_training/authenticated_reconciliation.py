"""Authenticated, bounded funding reconciliation with explicit coverage evidence.

Offline reference only; never an exchange order or portfolio execution path.
"""
from research.alphafold_training.authenticated_funding import verify_funding
from research.alphafold_training.funding_event_oracle import FundingEvent
from research.alphafold_training.funding_reconciliation import reconcile_funding

def reconcile_authenticated(trades, records, *, producer, epoch, dataset_version,
                            trusted_key, expected_mac, coverage_start_ns,
                            coverage_end_ns, fee_bps=0., slippage_bps=0.):
    rows = list(records)
    trades = list(trades)
    if type(coverage_start_ns) is not int or type(coverage_end_ns) is not int or coverage_start_ns < 0 or coverage_end_ns <= coverage_start_ns:
        raise ValueError("invalid coverage interval")
    if not trades:
        raise ValueError("empty trades")
    if min(t.start_ns for t in trades) < coverage_start_ns or max(t.end_ns for t in trades) > coverage_end_ns:
        raise ValueError("trades outside attested coverage")
    auth = verify_funding(rows, producer=producer, epoch=epoch,
                          dataset_version=dataset_version,
                          trusted_key=trusted_key, expected_mac=expected_mac)
    # Coverage boundaries must themselves be bound by the authenticated
    # producer manifest. Caller-supplied bounds alone are NOT proof of completeness.
    events = [FundingEvent(r.instrument, r.event_ns, r.rate) for r in rows]
    result = reconcile_funding(trades, events, fee_bps=fee_bps, slippage_bps=slippage_bps)
    result["funding_sha256"] = auth["sha256"]
    result["funding_authenticated"] = True
    result["coverage_completeness_verified"] = False
    result["real_oos_authorized"] = False
    return result
