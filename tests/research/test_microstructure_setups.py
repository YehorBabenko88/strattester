from strattester.research.microstructure import (
    AbsorptionMode,detect_absorption_proxy,detect_liquidity_sweep_reversal
)

def test_absorption_proxy_requires_aggression_without_price_progress():
    trades=[
      {'t':100,'price':100.00,'size':5,'side':'Sell'},
      {'t':110,'price':100.00,'size':7,'side':'Sell'},
      {'t':120,'price':99.99,'size':8,'side':'Sell'},
      {'t':130,'price':100.00,'size':4,'side':'Sell'},
      {'t':140,'price':100.01,'size':3,'side':'Buy'},
    ]
    x=detect_absorption_proxy(trades,level=100.0,tick_size=.01,known_at=150,min_aggressive_volume=20,max_penetration_ticks=2)
    assert x is not None
    assert x.mode is AbsorptionMode.ABSORPTION_PROXY
    assert x.side=='long'
    assert x.sell_volume>=20
    assert x.max_penetration_ticks<=2

def test_absorption_proxy_rejects_true_breakdown():
    trades=[
      {'t':100,'price':100.00,'size':10,'side':'Sell'},
      {'t':110,'price':99.95,'size':10,'side':'Sell'},
      {'t':120,'price':99.90,'size':10,'side':'Sell'},
    ]
    assert detect_absorption_proxy(trades,level=100,tick_size=.01,known_at=130,min_aggressive_volume=20,max_penetration_ticks=2) is None

def test_sweep_reversal_requires_return_through_level_and_sell_aggression():
    bars=[
      {'t':0,'open':99,'high':100,'low':98.8,'close':99.5},
      {'t':60,'open':99.5,'high':100.30,'low':99.4,'close':99.90},
    ]
    trades=[
      {'t':65,'price':100.25,'size':2,'side':'Buy'},
      {'t':80,'price':100.10,'size':4,'side':'Sell'},
      {'t':100,'price':99.95,'size':8,'side':'Sell'},
    ]
    x=detect_liquidity_sweep_reversal(bars,trades,level=100,direction='short',bar_ms=60,min_sweep_pct=.0015,max_sweep_pct=.004)
    assert x is not None and x.side=='short'
    assert x.known_at==120
    assert x.sweep_pct>=.0015
