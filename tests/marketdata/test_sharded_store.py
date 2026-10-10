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
    second.close()

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


def test_restart_resumes_partial_full_dataset_migration_idempotently(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([candle('BTCUSDT',0),candle('BTCUSDT',60_000),candle('BTCUSDT',120_000)])
    legacy.upsert_funding('BTCUSDT',[{'fundingRateTimestamp':0,'fundingRate':'0.0001'}])
    root=tmp_path/'shards'
    first=ShardedMarketStore(root,legacy_store=legacy)
    shard=first.for_symbol('BTCUSDT')
    shard.upsert_candles([candle('BTCUSDT',0)])
    first.manifest.set('BTCUSDT','MIGRATING',rows_copied=1)
    shard.checkpoint_wal('FULL')
    first.close()
    second=ShardedMarketStore(root,legacy_store=legacy)
    assert not second.manifest.ready('BTCUSDT')
    second.migrate_legacy_candles('BTCUSDT',batch_size=1)
    resumed=second.for_symbol('BTCUSDT')
    assert second.manifest.ready('BTCUSDT')
    assert resumed.coverage('BTCUSDT').count==3
    assert resumed.coverage('BTCUSDT','funding').count==1
    assert second._dataset_fingerprints(legacy,'BTCUSDT')==second._dataset_fingerprints(resumed,'BTCUSDT')
    second.close(); legacy.close()


def test_routed_wrapper_close_does_not_destroy_external_legacy_backend(tmp_path):
    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    store=ShardedMarketStore(tmp_path/'shards',legacy_store=legacy)
    store.close()
    assert legacy.connection.execute('SELECT 1').fetchone()[0]==1
    legacy.close()


def test_real_mid_migration_failure_resumes_without_duplicate_or_premature_promotion(tmp_path):
    """
    Simulate a process failure after one real committed candle batch.

    The partially populated shard must never become authoritative.  A fresh
    ShardedMarketStore instance must continue serving legacy data and an
    idempotent retry must converge to a validated SHARD_READY shard.
    """
    import pytest

    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')
    legacy.upsert_candles([
        candle('BTCUSDT',i*60_000)
        for i in range(10)
    ])

    root=tmp_path/'shards'
    first=ShardedMarketStore(root,legacy_store=legacy)
    shard=first.for_symbol('BTCUSDT')

    original_upsert=shard.upsert_candles
    calls={'count':0}

    def fail_after_first_committed_batch(records):
        calls['count']+=1

        if calls['count']==1:
            # This is a real SQLite transaction committed by upsert_candles().
            return original_upsert(records)

        raise OSError('synthetic process failure between committed batches')

    shard.upsert_candles=fail_after_first_committed_batch

    with pytest.raises(
        OSError,
        match='synthetic process failure between committed batches'
    ):
        first.migrate_legacy_candles(
            'BTCUSDT',
            batch_size=3,
        )

    # migrate_legacy_candles marks MIGRATING before copying and must never have
    # reached the validation/promotion boundary.
    record=first.manifest.get('BTCUSDT')
    assert record.state.value=='MIGRATING'
    assert not first.manifest.ready('BTCUSDT')

    # First committed batch physically exists in the target shard.
    assert original_upsert is not None
    assert shard.coverage('BTCUSDT').count==3
    assert shard.integrity_check()

    # But routed reads must still use the authoritative legacy database.
    assert first.coverage('BTCUSDT').count==10
    assert [
        x.open_time for x in first.iter_candles('BTCUSDT')
    ]==[
        i*60_000 for i in range(10)
    ]

    first.close()

    # Simulate restart: reopen the routed store against the same on-disk shard.
    second=ShardedMarketStore(root,legacy_store=legacy)

    assert not second.manifest.ready('BTCUSDT')
    assert second.coverage('BTCUSDT').count==10

    resumed_shard=second.for_symbol('BTCUSDT')

    # The three committed rows survived restart.
    assert resumed_shard.coverage('BTCUSDT').count==3
    assert resumed_shard.integrity_check()

    copied=second.migrate_legacy_candles(
        'BTCUSDT',
        batch_size=3,
    )

    # Existing rows are UPSERTed idempotently; final physical row count must
    # equal the source rather than source + already-copied rows.
    assert resumed_shard.coverage('BTCUSDT').count==10
    assert second.manifest.ready('BTCUSDT')

    record=second.manifest.get('BTCUSDT')
    assert record.state.value=='SHARD_READY'
    assert record.rows_copied==10

    assert second.coverage('BTCUSDT')==legacy.coverage('BTCUSDT')
    assert second._dataset_fingerprints(
        legacy,
        'BTCUSDT'
    )==second._dataset_fingerprints(
        resumed_shard,
        'BTCUSDT'
    )

    assert resumed_shard.integrity_check()

    # Retry once more even though the shard is complete.  Physical data must
    # remain exactly the same: no duplicate candles and no corruption.
    second.migrate_legacy_candles(
        'BTCUSDT',
        batch_size=3,
    )

    assert resumed_shard.coverage('BTCUSDT').count==10
    assert second.manifest.ready('BTCUSDT')
    assert resumed_shard.integrity_check()

    second.close()
    legacy.close()


def test_crash_during_ready_manifest_commit_recovers_without_exposing_uncommitted_promotion(tmp_path):
    """
    Simulate failure exactly when migration tries to persist SHARD_READY.

    At that point the physical shard is complete and validated, but authority
    must not switch unless the manifest promotion itself was durably committed.
    A restart/retry must safely complete the promotion.
    """
    import pytest
    from strattester.marketdata.shard_manifest import ShardState

    legacy=SQLiteMarketStore.open(tmp_path/'legacy.db')

    legacy.upsert_candles([
        candle('BTCUSDT',i*60_000)
        for i in range(10)
    ])

    legacy.upsert_funding(
        'BTCUSDT',
        [
            {
                'fundingRateTimestamp':0,
                'fundingRate':'0.0001',
            }
        ],
    )

    root=tmp_path/'shards'
    first=ShardedMarketStore(root,legacy_store=legacy)

    original_set=first.manifest.set
    injected={'done':False}

    def fail_ready_commit(symbol,state,*args,**kwargs):
        value=getattr(state,'value',state)

        if value=='SHARD_READY' and not injected['done']:
            injected['done']=True
            raise OSError('synthetic crash while committing SHARD_READY')

        return original_set(symbol,state,*args,**kwargs)

    first.manifest.set=fail_ready_commit

    with pytest.raises(
        OSError,
        match='synthetic crash while committing SHARD_READY'
    ):
        first.migrate_legacy_candles(
            'BTCUSDT',
            batch_size=3,
        )

    assert injected['done']

    shard=first.for_symbol('BTCUSDT')

    # Physical target was already completely copied and validated before the
    # failed manifest promotion.
    assert shard.coverage('BTCUSDT')==legacy.coverage('BTCUSDT')
    assert first._dataset_fingerprints(
        legacy,
        'BTCUSDT'
    )==first._dataset_fingerprints(
        shard,
        'BTCUSDT'
    )
    assert shard.integrity_check()

    # But SHARD_READY was never durably persisted, therefore authority must
    # remain with legacy.
    record=first.manifest.get('BTCUSDT')
    assert record is not None
    assert record.state is ShardState.MIGRATING
    assert not first.manifest.ready('BTCUSDT')

    assert first.coverage('BTCUSDT')==legacy.coverage('BTCUSDT')
    assert [
        x.open_time for x in first.iter_candles('BTCUSDT')
    ]==[
        i*60_000 for i in range(10)
    ]

    first.close()

    # Process restart.
    second=ShardedMarketStore(root,legacy_store=legacy)

    record=second.manifest.get('BTCUSDT')
    assert record is not None
    assert record.state is ShardState.MIGRATING
    assert not second.manifest.ready('BTCUSDT')

    reopened_shard=second.for_symbol('BTCUSDT')

    # Complete target survived, but is still deliberately non-authoritative.
    assert reopened_shard.coverage('BTCUSDT').count==10
    assert reopened_shard.coverage('BTCUSDT','funding').count==1
    assert reopened_shard.integrity_check()

    # Retry is idempotent and is now allowed to persist SHARD_READY.
    second.migrate_legacy_candles(
        'BTCUSDT',
        batch_size=3,
    )

    record=second.manifest.get('BTCUSDT')
    assert record.state is ShardState.SHARD_READY
    assert record.rows_copied==10
    assert second.manifest.ready('BTCUSDT')

    assert reopened_shard.coverage('BTCUSDT').count==10
    assert reopened_shard.coverage('BTCUSDT','funding').count==1

    assert second._dataset_fingerprints(
        legacy,
        'BTCUSDT'
    )==second._dataset_fingerprints(
        reopened_shard,
        'BTCUSDT'
    )

    assert reopened_shard.integrity_check()

    second.close()
    legacy.close()
