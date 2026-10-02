from strattester.research.orderflow import cumulative_delta,aggression_decay,cvd_divergence

def test_cumulative_delta_is_causal():
    rows=[{'t':0,'buy_volume':3,'sell_volume':5},{'t':60,'buy_volume':8,'sell_volume':2}]
    out=cumulative_delta(rows)
    assert [x['cvd'] for x in out]==[-2,4]

def test_sell_aggression_decay_detects_falling_pressure():
    rows=[
      {'t':0,'buy_volume':1,'sell_volume':10},
      {'t':60,'buy_volume':1,'sell_volume':7},
      {'t':120,'buy_volume':1,'sell_volume':3},
    ]
    x=aggression_decay(rows,side='sell',window=3)
    assert x is not None and x['decaying'] and x['known_at']==120

def test_bullish_cvd_divergence_requires_price_not_lower_but_cvd_higher():
    points=[
      {'t':0,'price':100,'cvd':-10},
      {'t':60,'price':99,'cvd':-20},
      {'t':120,'price':99.2,'cvd':-12},
    ]
    assert cvd_divergence(points,direction='bullish',lookback=3)
