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


def test_promotion_copies_and_verifies_all_auxiliary_datasets(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',0)])
    legacy.upsert_price_klines('mark_price','BTCUSDT',[[0,1,1.1,.9,1]],'1m')
    legacy.upsert_price_klines('index_price','BTCUSDT',[[0,2,2.1,1.9,2]],'1m')
    legacy.upsert_price_klines('premium_index','BTCUSDT',[[0,.01,.02,.005,.01]],'1m')
    legacy.upsert_open_interest('BTCUSDT',[{'timestamp':0,'openInterest':'123'}])
    legacy.upsert_funding('BTCUSDT',[{'fundingRateTimestamp':0,'fundingRate':'0.0001'}])
    legacy.upsert_long_short_ratio('BTCUSDT',[{'timestamp':0,'buyRatio':'0.6','sellRatio':'0.4'}])
    legacy.upsert_public_trade_aggregates('BTCUSDT',[{'open_time':0,'buy_volume':2,'sell_volume':1,'turnover':3,'trade_count':2}])
    store=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    store.migrate_legacy_candles('BTCUSDT')
    shard=store.for_symbol('BTCUSDT')
    assert store.manifest.ready('BTCUSDT')
    assert store._dataset_fingerprints(legacy,'BTCUSDT')==store._dataset_fingerprints(shard,'BTCUSDT')
    for dataset,tf in [('mark_price','1m'),('index_price','1m'),('premium_index','1m'),
                       ('open_interest','5m'),('funding','1m'),('long_short_ratio','5m'),
                       ('public_trade_aggregates','1m')]:
        assert shard.coverage('BTCUSDT',dataset,tf).count==1
    store.close(); legacy.close()


def test_symbol_with_auxiliary_data_but_no_candles_is_not_promoted_empty(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_funding('BTCUSDT',[{'fundingRateTimestamp':0,'fundingRate':'0.0001'}])
    store=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    store.migrate_legacy_candles('BTCUSDT')
    shard=store.for_symbol('BTCUSDT')
    assert store.manifest.ready('BTCUSDT')
    assert shard.coverage('BTCUSDT','funding').count==1
    assert store._dataset_fingerprints(legacy,'BTCUSDT')==store._dataset_fingerprints(shard,'BTCUSDT')
    store.close(); legacy.close()
