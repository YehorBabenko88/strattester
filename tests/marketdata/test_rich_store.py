from strattester.marketdata.sqlite_store import SQLiteMarketStore

def test_rich_store_upserts_market_price_and_reports_coverage(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    n=s.upsert_price_klines('mark_price','BTCUSDT',[
      ['0','100','101','99','100'],['60000','100','102','99','101']],timeframe='1m')
    assert n.accepted==2
    c=s.coverage('BTCUSDT','mark_price','1m',60000)
    assert c.count==2 and c.earliest==0 and c.latest==60000
    s.close()

def test_rich_store_upserts_oi_funding_ratio_idempotently(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    a=s.upsert_open_interest('BTCUSDT',[{'timestamp':'0','openInterest':'123.4'}],timeframe='5m')
    b=s.upsert_funding('BTCUSDT',[{'fundingRateTimestamp':'0','fundingRate':'0.0001'}])
    c=s.upsert_long_short_ratio('BTCUSDT',[{'timestamp':'0','buyRatio':'0.55','sellRatio':'0.45'}],timeframe='5m')
    assert (a.accepted,b.accepted,c.accepted)==(1,1,1)
    assert s.upsert_open_interest('BTCUSDT',[{'timestamp':'0','openInterest':'123.4'}],timeframe='5m').unchanged==1
    assert s.coverage('BTCUSDT','open_interest','5m',300000).count==1
    assert s.coverage('BTCUSDT','funding','funding',1).count==1
    assert s.coverage('BTCUSDT','long_short_ratio','5m',300000).count==1
    s.close()
