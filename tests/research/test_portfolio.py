from types import SimpleNamespace
from strattester.research.portfolio import PortfolioPolicy,build_portfolio

def T(symbol,entry,exit,net,fees=0):
    return SimpleNamespace(entry_time=entry,exit_time=exit,net_pnl=net,fees=fees,metadata={'symbol':symbol})

def test_portfolio_accepts_only_one_overlapping_trade_globally():
    xs=[T('BTCUSDT',100,200,10),T('ETHUSDT',150,180,50),T('SOLUSDT',200,250,-5)]
    p=build_portfolio(xs,PortfolioPolicy(initial_capital=1000,max_open_positions=1))
    assert [x.metadata['symbol'] for x in p.accepted]==['BTCUSDT','SOLUSDT']
    assert len(p.rejected)==1
    assert p.final_capital==1005

def test_portfolio_capital_is_chronological_not_strategy_order():
    xs=[T('LATE',200,250,20),T('EARLY',0,100,-10)]
    p=build_portfolio(xs,PortfolioPolicy(initial_capital=1000,max_open_positions=1))
    assert [x.metadata['symbol'] for x in p.accepted]==['EARLY','LATE']
    assert p.final_capital==1010
