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
    assert s.manifest.ready('BTCUSDT')
    shard=s.for_symbol('BTCUSDT')
    assert shard.coverage('BTCUSDT').count==5
    assert shard.integrity_check()
    assert [x.open_time for x in s.iter_candles('BTCUSDT')]==[i*60_000 for i in range(5)]
    s.close(); legacy.close()


def test_partial_shard_is_never_authoritative_after_restart(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',i*60_000) for i in range(5)])
    root=tmp_path/'shards'
    first=ShardedMarketStore(root,legacy_store=legacy)
    first.for_symbol('BTCUSDT').upsert_candles([candle('BTCUSDT',0),candle('BTCUSDT',60_000)])
    first.manifest.set('BTCUSDT','MIGRATING',rows_copied=2)
    first.close()
    second=ShardedMarketStore(root,legacy_store=legacy)
    assert second.manifest.ready('BTCUSDT') is False
    assert second.coverage('BTCUSDT').count==5
    assert [x.open_time for x in second.iter_candles('BTCUSDT')]==[i*60_000 for i in range(5)]
    second.close(); legacy.close()

def test_migration_resume_is_idempotent_and_promotes_only_after_validation(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',i*60_000) for i in range(5)])
    root=tmp_path/'shards'
    first=ShardedMarketStore(root,legacy_store=legacy)
    first.for_symbol('BTCUSDT').upsert_candles([candle('BTCUSDT',0),candle('BTCUSDT',60_000)])
    first.manifest.set('BTCUSDT','MIGRATING',rows_copied=2)
    first.close()
    second=ShardedMarketStore(root,legacy_store=legacy)
    copied=second.migrate_legacy_candles('BTCUSDT',batch_size=2)
    assert copied==3
    record=second.manifest.get('BTCUSDT')
    assert record.state.value=='SHARD_READY' and record.rows_copied==5
    assert second.coverage('BTCUSDT').count==5
    second.close(); legacy.close()


def test_live_writes_stay_visible_in_legacy_until_promotion(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',0)])
    store=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    store.manifest.set('BTCUSDT','MIGRATING')
    store.upsert_candles([candle('BTCUSDT',60_000)])
    assert legacy.coverage('BTCUSDT').count==2
    assert store.coverage('BTCUSDT').count==2
    assert store.for_symbol('BTCUSDT').coverage('BTCUSDT').count==0
    store.close(); legacy.close()

def test_writes_switch_to_shard_only_after_ready(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',0)])
    store=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    store.migrate_legacy_candles('BTCUSDT')
    assert store.manifest.ready('BTCUSDT')
    store.upsert_candles([candle('BTCUSDT',60_000)])
    assert legacy.coverage('BTCUSDT').count==1
    assert store.for_symbol('BTCUSDT').coverage('BTCUSDT').count==2
    assert store.coverage('BTCUSDT').count==2
    store.close(); legacy.close()


def test_source_growth_during_migration_defers_promotion_and_retry_catches_up(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',0),candle('BTCUSDT',60_000)])
    store=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    original=legacy.iter_candles
    injected={'done':False}
    def growing(*args,**kwargs):
        for row in original(*args,**kwargs):
            yield row
            if not injected['done']:
                injected['done']=True
                legacy.upsert_candles([candle('BTCUSDT',120_000)])
    legacy.iter_candles=growing
    import pytest
    with pytest.raises(RuntimeError,match='source changed'):
        store.migrate_legacy_candles('BTCUSDT',batch_size=1)
    assert not store.manifest.ready('BTCUSDT')
    assert store.coverage('BTCUSDT').count==3
    legacy.iter_candles=original
    store.migrate_legacy_candles('BTCUSDT',batch_size=1)
    assert store.manifest.ready('BTCUSDT')
    assert store.coverage('BTCUSDT').count==3
    store.close(); legacy.close()
