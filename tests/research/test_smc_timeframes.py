from strattester.research.smc import build_mtf_structure, SMCContext

def bars(step, highs, lows, closes):
    out=[]
    prev=closes[0]
    for i,(h,l,c) in enumerate(zip(highs,lows,closes)):
        out.append({'t':i*step,'open':prev,'high':h,'low':l,'close':c})
        prev=c
    return out

def test_mtf_events_keep_source_timeframe():
    m5=bars(300_000,[9,10,9.5,11],[7,8,8,9],[8,9,9,10.5])
    out=build_mtf_structure({'5m':m5},left=1,right=1)
    assert out and all(x.timeframe=='5m' for x in out)

def test_higher_timeframe_bias_is_only_visible_after_confirmation():
    h1=bars(3_600_000,[9,10,9.5,11],[7,8,8,9],[8,9,9,10.5])
    m5=bars(300_000,[9,10,9.5,11],[7,8,8,9],[8,9,9,10.5])
    ctx=SMCContext(build_mtf_structure({'1h':h1,'5m':m5},left=1,right=1))
    assert ctx.bias_at(1000,'1h') is None
    assert ctx.bias_at(4*3_600_000,'1h')=='bullish'

def test_lower_tf_entry_can_require_confirmed_higher_tf_bias():
    h1=bars(3_600_000,[9,10,9.5,11],[7,8,8,9],[8,9,9,10.5])
    m5=bars(300_000,[9,10,9.5,11],[7,8,8,9],[8,9,9,10.5])
    ctx=SMCContext(build_mtf_structure({'1h':h1,'5m':m5},left=1,right=1))
    assert not ctx.entry_allowed(1000,entry_timeframe='5m',bias_timeframe='1h',direction='bullish')
    assert ctx.entry_allowed(4*3_600_000,entry_timeframe='5m',bias_timeframe='1h',direction='bullish')
