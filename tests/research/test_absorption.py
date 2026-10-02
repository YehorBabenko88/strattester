from strattester.research.absorption import AbsorptionConfig,detect_absorption_setup

def test_absorption_requires_level_aggression_stall_decay_and_cvd_confirmation():
    rows=[
      {'t':0,'buy_volume':1,'sell_volume':12,'price':100.00},
      {'t':60,'buy_volume':2,'sell_volume':8,'price':99.99},
      {'t':120,'buy_volume':5,'sell_volume':4,'price':100.01},
    ]
    x=detect_absorption_setup(rows,level=100,tick_size=.01,direction='long',
        config=AbsorptionConfig(min_sell_volume=20,max_penetration_ticks=2))
    assert x is not None
    assert x.direction=='long' and x.known_at==120
    assert x.entry_price>=100

def test_absorption_rejects_when_price_accepts_below_wall():
    rows=[
      {'t':0,'buy_volume':1,'sell_volume':12,'price':100},
      {'t':60,'buy_volume':1,'sell_volume':10,'price':99.95},
      {'t':120,'buy_volume':2,'sell_volume':8,'price':99.94},
    ]
    assert detect_absorption_setup(rows,level=100,tick_size=.01,direction='long',
        config=AbsorptionConfig(min_sell_volume=20,max_penetration_ticks=2)) is None
