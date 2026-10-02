from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_coverage_detects_internal_gap(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([
        Candle('BTCUSDT','1m',0,1,1,1,1,1),
        Candle('BTCUSDT','1m',60_000,1,1,1,1,1),
        Candle('BTCUSDT','1m',180_000,1,1,1,1,1),
    ])
    cov=s.coverage('BTCUSDT')
    assert cov.earliest==0 and cov.latest==180_000 and cov.count==3
    assert [(g.start,g.end) for g in cov.gaps]==[(120_000,120_000)]
    s.close()
