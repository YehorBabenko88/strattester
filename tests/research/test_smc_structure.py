from strattester.research.smc import market_structure

def test_bos_known_only_on_breaking_bar_close():
    bars=[
      {'t':0,'open':8,'high':9,'low':7,'close':8},
      {'t':60,'open':8,'high':10,'low':8,'close':9},
      {'t':120,'open':9,'high':9.5,'low':8,'close':9},
      {'t':180,'open':9,'high':11,'low':9,'close':10.5},
    ]
    out=market_structure(bars,bar_ms=60,left=1,right=1)
    bos=[x for x in out if x.kind=='bullish_bos']
    assert len(bos)==1 and bos[0].event_time==180 and bos[0].known_at==240

def test_liquidity_sweep_requires_rejection_back_through_level():
    bars=[
      {'t':0,'open':8,'high':9,'low':7,'close':8},
      {'t':60,'open':8,'high':10,'low':8,'close':9},
      {'t':120,'open':9,'high':9.5,'low':8,'close':9},
      {'t':180,'open':9,'high':10.5,'low':8.8,'close':9.5},
    ]
    out=market_structure(bars,bar_ms=60,left=1,right=1)
    sweep=[x for x in out if x.kind=='bearish_liquidity_sweep']
    assert len(sweep)==1 and sweep[0].known_at==240

def test_order_block_is_created_only_after_confirming_bos():
    bars=[
      {'t':0,'open':8,'high':9,'low':7,'close':8.5},
      {'t':60,'open':9.5,'high':10,'low':8,'close':8.5},
      {'t':120,'open':8.5,'high':9.5,'low':8,'close':9},
      {'t':180,'open':9,'high':11,'low':8.9,'close':10.5},
    ]
    out=market_structure(bars,bar_ms=60,left=1,right=1)
    ob=[x for x in out if x.kind=='bullish_order_block']
    assert len(ob)==1
    assert ob[0].event_time==60 and ob[0].known_at==240


def test_same_confirmed_swing_can_break_only_once():
    bars=[
      {'t':0,'open':8,'high':9,'low':7,'close':8},
      {'t':60,'open':8,'high':10,'low':8,'close':9},
      {'t':120,'open':9,'high':9.5,'low':8,'close':9},
      {'t':180,'open':9,'high':11,'low':9,'close':10.5},
      {'t':240,'open':10.5,'high':12,'low':10,'close':11.5},
    ]
    out=market_structure(bars,bar_ms=60,left=1,right=1)
    breaks=[x for x in out if x.kind in ('bullish_bos','bullish_choch') and x.value.get('level')==10]
    assert len(breaks)==1
