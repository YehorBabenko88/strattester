from types import SimpleNamespace
from strattester.research.portfolio import PortfolioPolicy,build_portfolio

def T(symbol,strategy,entry,exit,net):
    return SimpleNamespace(entry_time=entry,exit_time=exit,net_pnl=net,fees=0,
        metadata={'symbol':symbol,'strategy_id':strategy})

def test_one_open_trade_is_enforced_per_instrument_and_strategy():
    xs=[
      T('BTCUSDT','A',100,200,10),
      T('BTCUSDT','A',150,180,50),
      T('BTCUSDT','B',150,180,20),
      T('ETHUSDT','A',150,180,30),
      T('BTCUSDT','A',200,250,-5),
    ]
    p=build_portfolio(xs,PortfolioPolicy(initial_capital=1000,max_open_positions_per_stream=1))
    accepted={(x.metadata['symbol'],x.metadata['strategy_id'],x.entry_time) for x in p.accepted}
    assert ('BTCUSDT','A',150) not in accepted
    assert ('BTCUSDT','B',150) in accepted
    assert ('ETHUSDT','A',150) in accepted
    assert ('BTCUSDT','A',200) in accepted
    assert len(p.rejected)==1

def test_each_strategy_instrument_stream_has_independent_virtual_capital():
    xs=[T('BTCUSDT','A',0,100,10),T('BTCUSDT','B',0,100,-20)]
    p=build_portfolio(xs,PortfolioPolicy(initial_capital=1000,max_open_positions_per_stream=1))
    assert p.final_capital[('BTCUSDT','A')]==1010
    assert p.final_capital[('BTCUSDT','B')]==980
