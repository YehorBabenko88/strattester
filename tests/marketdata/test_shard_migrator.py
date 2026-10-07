from strattester.marketdata.shard_migrator import ShardMigrator
from strattester.marketdata.sharded_store import ShardedMarketStore
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_migrator_processes_bounded_batches_and_resumes(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    symbols=['BTCUSDT','ETHUSDT','SOLUSDT']
    for symbol in symbols:
        legacy.upsert_candles([Candle(symbol,'1m',i*60_000,1,1.1,.9,1,1) for i in range(3)])
    store=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    migrator=ShardMigrator(store)
    first=migrator.migrate_batch(symbols,limit=2,batch_size=2)
    assert (first.attempted,first.ready,first.failed)==(2,2,0)
    assert store.manifest.ready('BTCUSDT') and store.manifest.ready('ETHUSDT')
    assert not store.manifest.ready('SOLUSDT')
    second=migrator.migrate_batch(symbols,limit=2,batch_size=2)
    assert (second.attempted,second.ready,second.failed)==(1,1,0)
    assert store.manifest.ready('SOLUSDT')
    store.close(); legacy.close()
