from strattester.research.volume_profile import POCMode,trade_profile,proxy_profile

def test_trade_profile_labels_true_trade_mode():
    trades=[{'t':1,'price':100,'volume':2},{'t':2,'price':101,'volume':1},{'t':3,'price':100,'volume':3}]
    x=trade_profile(trades,known_at=10)
    assert x.mode is POCMode.TRADE_POC and x.poc==100 and x.known_at==10

def test_proxy_profile_is_explicitly_approximate():
    bars=[{'t':0,'high':101,'low':99,'close':100,'volume':5}]
    x=proxy_profile(bars,known_at=60)
    assert x.mode is POCMode.POC_PROXY

def test_future_trades_do_not_change_frozen_profile():
    base=[{'t':1,'price':100,'volume':5},{'t':2,'price':101,'volume':1}]
    a=trade_profile(base,known_at=10)
    b=trade_profile(base+[{'t':11,'price':200,'volume':100}],known_at=10)
    assert a==b
