from pathlib import Path
from strattester.config import AppConfig
from strattester.marketdata.store_factory import open_configured_market_store
from strattester.marketdata.sharded_store import ShardedMarketStore
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_configured_store_routes_research_reads_after_promotion(tmp_path):
    cfg=AppConfig.load(tmp_path)
    cfg.ensure_directories()
    legacy=SQLiteMarketStore.open(cfg.market_db)
    legacy.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1)])
    legacy.close()
    object.__setattr__(cfg,'market_shards_dir',tmp_path/'data'/'market-shards')
    store=open_configured_market_store(cfg)
    assert isinstance(store,ShardedMarketStore)
    store.migrate_legacy_candles('BTCUSDT')
    store.upsert_candles([Candle('BTCUSDT','1m',60_000,1,1,1,1,1)])
    assert [x.open_time for x in store.iter_candles('BTCUSDT')]==[0,60_000]
    store.close()
    store.legacy_store.close()
