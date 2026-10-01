from strattester.research.levels import completed_period_levels
from strattester.research.smc import confirmed_swings,fair_value_gaps

def test_completed_level_known_only_after_period_close():
    bars=[{'t':0,'high':10,'low':5},{'t':60,'high':12,'low':6}]
    out=completed_period_levels(bars,period_ms=120,next_bar_ms=60)
    high=[x for x in out if x.kind=='period_high'][0]
    assert high.event_time==60 and high.known_at==120 and high.value==12

def test_swing_high_known_after_right_confirmation():
    bars=[{'t':0,'high':1,'low':0},{'t':60,'high':3,'low':1},{'t':120,'high':2,'low':1}]
    x=[x for x in confirmed_swings(bars,left=1,right=1) if x.kind=='swing_high'][0]
    assert x.event_time==60 and x.known_at==120

def test_fvg_known_at_third_candle_close():
    bars=[{'t':0,'high':10,'low':8},{'t':60,'high':12,'low':10},{'t':120,'high':15,'low':13}]
    x=fair_value_gaps(bars,bar_ms=60)[0]
    assert x.kind=='bullish_fvg' and x.event_time==120 and x.known_at==180
    assert x.value=={'low':10,'high':13}
