from strattester.research.scalp_bootstrap import historical_scalp_events

def bars(n=40):
    out=[];p=100.0
    for i in range(n):
        out.append({"t":i*60000,"open":p,"high":p+1,"low":p-1,"close":p+(.2 if i%2 else -.2),
                    "volume":100+(i%5)*50,"turnover":10000})
        p=out[-1]["close"]
    return out

def test_historical_scalp_contract_never_fabricates_l2():
    xs=historical_scalp_events(bars(),symbol="BTCUSDT")
    for x in xs:
        assert x["capability_scope"]=="HISTORICAL_NO_L2"
        f=x["features"]
        for k in ("book_imbalance","book_velocity","cancel_rate","wall_ratio","wall_replenishment","spread_bps"):
            assert f[k] is None

def test_historical_scalp_known_at_is_after_event():
    xs=historical_scalp_events(bars(),symbol="BTCUSDT")
    assert all(x["known_at_ms"]>=x["event_ts_ms"] for x in xs)
