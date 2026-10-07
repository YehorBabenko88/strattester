from strattester.marketdata.sharded_store import ShardedMarketStore
from strattester.marketdata.sqlite_store import Candle,SQLiteMarketStore

def candle(symbol,t=0):
    return Candle(symbol,'1m',t,1,1.1,.9,1,1)

def test_symbols_use_independent_sqlite_files(tmp_path):
    s=ShardedMarketStore(tmp_path/'shards',buckets=8)
    s.upsert_candles([candle('BTCUSDT')])
    s.upsert_candles([candle('ETHUSDT')])
    assert s.shard_path('BTCUSDT')!=s.shard_path('ETHUSDT')
    assert s.shard_path('BTCUSDT').exists()
    assert s.shard_path('ETHUSDT').exists()
    assert s.coverage('BTCUSDT').count==1
    assert s.coverage('ETHUSDT').count==1
    assert s.integrity_check()
    s.close()

def test_legacy_database_remains_read_fallback_until_shard_has_data(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',0),candle('BTCUSDT',60_000)])
    s=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    assert s.coverage('BTCUSDT').count==2
    assert [x.open_time for x in s.iter_candles('BTCUSDT')]==[0,60_000]
    s.close(); legacy.close()

def test_write_batch_cannot_cross_symbol_shards(tmp_path):
    s=ShardedMarketStore(tmp_path/'shards')
    try:
        s.upsert_candles([candle('BTCUSDT'),candle('ETHUSDT')])
    except ValueError:
        pass
    else:
        raise AssertionError('mixed-symbol write must be rejected')
    s.close()


def test_legacy_symbol_migration_is_validated_before_shard_use(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',i*60_000) for i in range(5)])
    s=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    copied=s.migrate_legacy_candles('BTCUSDT')
    assert copied==5
    shard=s.for_symbol('BTCUSDT')
    assert shard.coverage('BTCUSDT').count==5
    assert shard.integrity_check()
    assert [x.open_time for x in s.iter_candles('BTCUSDT')]==[i*60_000 for i in range(5)]
    s.close(); legacy.close()
