"""Offline ledger reconciliation: flat stress cost versus signed historical funding.

This module does not claim actual market fills, funding provenance or portfolio PnL.
"""
from research.alphafold_training.funding_event_oracle import funding_cashflow, FundingEvent
from research.alphafold_training.system_audit_oracles import oracle_ledger

def reconcile_funding(trades, events, *, fee_bps=0., slippage_bps=0.):
    trades = list(trades)
    events = list(events)
    if not trades:
        raise ValueError("empty trade ledger")
    # Validate every event, even those outside the evaluated trade horizons.
    import math
    seen_events = set()
    for event in events:
        if not isinstance(event, FundingEvent):
            raise ValueError("invalid funding event")
        if not event.instrument or type(event.timestamp_ns) is not int or event.timestamp_ns < 0:
            raise ValueError("invalid funding event identity")
        if type(event.rate) not in (int, float) or not math.isfinite(event.rate):
            raise ValueError("invalid funding rate")
        key = (event.instrument, event.timestamp_ns)
        if key in seen_events:
            raise ValueError("duplicate funding event")
        seen_events.add(key)
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
