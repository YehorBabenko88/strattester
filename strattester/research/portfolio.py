from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PortfolioPolicy:
    initial_capital:float=10_000.0
    max_open_positions_per_stream:int=1

@dataclass(frozen=True)
class PortfolioResult:
    initial_capital:float
    final_capital:dict
    accepted:tuple
    rejected:tuple
    equity_curve:dict

def _stream_key(trade):
    md=getattr(trade,'metadata',{}) or {}
    symbol=md.get('symbol'); strategy=md.get('strategy_id')
    if not symbol or not strategy:
        raise ValueError('trade metadata must contain symbol and strategy_id')
    return str(symbol),str(strategy)

def build_portfolio(trades,policy:PortfolioPolicy=PortfolioPolicy())->PortfolioResult:
    if policy.initial_capital<0: raise ValueError('initial_capital')
    if policy.max_open_positions_per_stream!=1:
        raise ValueError('only one open trade per instrument/strategy stream is supported')
    ordered=sorted(trades,key=lambda x:(int(x.entry_time),int(x.exit_time),_stream_key(x)))
    accepted=[]; rejected=[]; busy_until={}; capital={}; equity={}
    for trade in ordered:
        key=_stream_key(trade); entry=int(trade.entry_time); exit_time=int(trade.exit_time)
        if exit_time<entry: raise ValueError('trade exits before entry')
        if key in busy_until and entry<busy_until[key]:
            rejected.append(trade); continue
        accepted.append(trade)
        capital.setdefault(key,float(policy.initial_capital))
        equity.setdefault(key,[])
        capital[key]+=float(trade.net_pnl)
        busy_until[key]=exit_time
        equity[key].append((exit_time,capital[key]))
    return PortfolioResult(float(policy.initial_capital),capital,tuple(accepted),tuple(rejected),
        {k:tuple(v) for k,v in equity.items()})
