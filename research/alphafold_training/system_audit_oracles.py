"""Independent reference oracle for the candidate's conservative roundtrip ledger.

No exchange calls, trading, production storage or model execution.
"""
import math
from statistics import mean

def oracle_ledger(trades, fee_bps=0., slippage_bps=0., funding_bps=0.):
    if not trades:
        raise ValueError("empty ledger")
    for cost in (fee_bps, slippage_bps, funding_bps):
        if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
            raise ValueError("invalid cost")
    previous = {}
    results = []
    turnover = 0
    for trade in sorted(trades, key=lambda t: (t.start_ns, t.instrument)):
        if type(trade.start_ns) is not int or type(trade.end_ns) is not int:
            raise ValueError("invalid timestamp")
        if (not trade.instrument or trade.end_ns <= trade.start_ns
                or trade.start_ns < previous.get(trade.instrument, -1)
                or type(trade.position) is not int or trade.position not in (-1, 0, 1)
                or type(trade.simple_return) not in (int, float)
                or not math.isfinite(trade.simple_return) or trade.simple_return < -1):
            raise ValueError("invalid or overlapping trade")
        previous[trade.instrument] = trade.end_ns
        units = abs(trade.position)
        turnover += 2 * units
        gross = trade.position * trade.simple_return
        entry_cost = units * (fee_bps + slippage_bps) / 10000
        exit_cost = units * (fee_bps + slippage_bps) / 10000
        funding_cost = units * funding_bps / 10000
        results.append(gross - entry_cost - exit_cost - funding_cost)
    return {"returns": results, "turnover": turnover, "mean": mean(results)}

def oracle_gaussian_nll(mu, sigma, target):
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (mu, sigma, target)) or sigma <= 0:
        raise ValueError("invalid distribution")
    return .5 * math.log(2 * math.pi) + math.log(sigma) + .5 * ((target - mu) / sigma) ** 2
