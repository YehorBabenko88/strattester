from strattester.marketdata.readiness import requirements_for_instrument

def test_instrument_history_plan_starts_at_launch_and_uses_dataset_cadence():
    inst={'symbol':'BTCUSDT','launchTime':'1','fundingInterval':'480'}
    reqs={r.dataset:r for r in requirements_for_instrument(inst,end_ms=1_000_000)}
    assert reqs['candles'].start_ms==60_000 and reqs['candles'].timeframe=='1m'
    assert reqs['mark_price'].timeframe=='1m'
    assert reqs['open_interest'].timeframe=='5m'
    assert reqs['funding'].timeframe=='480m'
    assert reqs['long_short_ratio'].timeframe=='5m'
