"""Offline ledger reconciliation: flat stress cost versus signed historical funding.

This module does not claim actual market fills, funding provenance or portfolio PnL.
"""
from research.alphafold_training.funding_event_oracle import funding_cashflow
from research.alphafold_training.system_audit_oracles import oracle_ledger

def reconcile_funding(trades, events, *, fee_bps=0., slippage_bps=0.):
    trades = list(trades)
    events = list(events)
    if not trades:
        raise ValueError("empty trade ledger")
    baseline = oracle_ledger(trades, fee_bps, slippage_bps, 0.)
    adjusted = []
    cashflows = []
    for trade, gross_net in zip(sorted(trades, key=lambda t: (t.start_ns, t.instrument)), baseline["returns"]):
        cashflow = funding_cashflow(trade.position, trade.start_ns, trade.end_ns, trade.instrument, events)
        cashflows.append(cashflow)
        adjusted.append(gross_net + cashflow)
    return {
        "status": "OFFLINE_REFERENCE_ONLY",
        "funding_event_count": len(events),
        "funding_cashflows": cashflows,
        "net_returns": adjusted,
        "turnover": baseline["turnover"],
        "provenance_verified": False,
        "portfolio_pnl_authorized": False,
    }
