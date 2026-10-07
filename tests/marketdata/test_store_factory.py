from strattester.marketdata.store_factory import open_market_store
from strattester.marketdata.sharded_store import ShardedMarketStore
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_factory_uses_shards_without_creating_empty_legacy(tmp_path):
    market=tmp_path/'missing.sqlite3'
    store=open_market_store(market,tmp_path/'shards')
    assert isinstance(store,ShardedMarketStore)
    assert not market.exists()
    store.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1)])
    assert store.coverage('BTCUSDT').count==1
    store.close()
    assert not market.exists()

def test_factory_preserves_existing_legacy_until_symbol_promotion(tmp_path):
    market=tmp_path/'market.sqlite3'
    legacy=SQLiteMarketStore.open(market)
    legacy.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1)])
    legacy.close()
    store=open_market_store(market,tmp_path/'shards')
    store.upsert_candles([Candle('BTCUSDT','1m',60_000,1,1,1,1,1)])
    assert store.legacy_store.coverage('BTCUSDT').count==2
    assert store.for_symbol('BTCUSDT').coverage('BTCUSDT').count==0
    store.migrate_legacy_candles('BTCUSDT')
    store.upsert_candles([Candle('BTCUSDT','1m',120_000,1,1,1,1,1)])
    assert store.legacy_store.coverage('BTCUSDT').count==2
    assert store.for_symbol('BTCUSDT').coverage('BTCUSDT').count==3
    store.close()
