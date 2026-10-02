from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PortfolioPolicy:
    initial_capital:float=10_000.0
    max_open_positions:int=1

@dataclass(frozen=True)
class PortfolioResult:
    initial_capital:float
    final_capital:float
    accepted:tuple
    rejected:tuple
    equity_curve:tuple

def build_portfolio(trades,policy:PortfolioPolicy=PortfolioPolicy())->PortfolioResult:
    if policy.initial_capital<0: raise ValueError('initial_capital')
    if policy.max_open_positions!=1:
        raise ValueError('only max_open_positions=1 is currently supported')
    ordered=sorted(trades,key=lambda x:(int(x.entry_time),int(x.exit_time)))
    accepted=[]; rejected=[]; equity=[]; capital=float(policy.initial_capital); busy_until=None
    for trade in ordered:
        entry=int(trade.entry_time); exit_time=int(trade.exit_time)
        if exit_time<entry: raise ValueError('trade exits before entry')
        if busy_until is not None and entry<busy_until:
            rejected.append(trade); continue
        accepted.append(trade)
        capital+=float(trade.net_pnl)
        busy_until=exit_time
        equity.append((exit_time,capital))
    return PortfolioResult(float(policy.initial_capital),capital,tuple(accepted),tuple(rejected),tuple(equity))
