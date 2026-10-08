from __future__ import annotations
import subprocess,sys,textwrap
from strattester.marketdata.sqlite_store import SQLiteMarketStore

def _kill_writer(db,commit):
    code=textwrap.dedent(f"""
        import os,sqlite3
        from pathlib import Path
        from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
        s=SQLiteMarketStore.open(Path(r'{str(db)}'))
        s.connection.execute('BEGIN IMMEDIATE')
        s.connection.execute(
            "INSERT INTO candles(symbol,timeframe,open_time,open,high,low,close,volume,turnover,complete) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ('BTCUSDT','1m',60000,1,1,1,1,1,None,1))
        {"s.connection.commit()" if commit else ""}
        os._exit(23)
    """)
    return subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)

def test_os_hard_kill_rolls_back_uncommitted_wal_transaction(tmp_path):
    db=tmp_path/'market.db'
    s=SQLiteMarketStore.open(db); s.close()
    result=_kill_writer(db,False)
    assert result.returncode==23
    reopened=SQLiteMarketStore.open(db)
    assert reopened.coverage('BTCUSDT').count==0
    assert reopened.integrity_check()
    reopened.close()

def test_os_hard_kill_preserves_committed_wal_transaction(tmp_path):
    db=tmp_path/'market.db'
    s=SQLiteMarketStore.open(db); s.close()
    result=_kill_writer(db,True)
    assert result.returncode==23
    reopened=SQLiteMarketStore.open(db)
    assert reopened.coverage('BTCUSDT').count==1
    assert reopened.integrity_check()
    reopened.close()


def test_os_hard_kill_mid_shard_migration_recovers_idempotently(tmp_path):
    """
    A child process is terminated with os._exit immediately after the first
    committed shard batch.

    No normal close(), checkpoint or finally block runs.  After restart the
    partial shard must remain non-authoritative and an idempotent migration
    retry must converge to exactly the legacy dataset.
    """
    from pathlib import Path
    from strattester.marketdata.sqlite_store import Candle
    from strattester.marketdata.sharded_store import ShardedMarketStore
    from strattester.marketdata.shard_manifest import ShardState

    legacy_path=tmp_path/'legacy.db'
    shard_root=tmp_path/'shards'

    legacy=SQLiteMarketStore.open(legacy_path)
    legacy.upsert_candles([
        Candle(
            'BTCUSDT',
            '1m',
            i*60_000,
            1,
            1.1,
            .9,
            1,
            1,
        )
        for i in range(25)
    ])
    legacy.close()

    code=textwrap.dedent(r"""
        import os
        import sys
        from pathlib import Path

        from strattester.marketdata.sqlite_store import SQLiteMarketStore
        from strattester.marketdata.sharded_store import ShardedMarketStore

        legacy_path=Path(sys.argv[1])
        shard_root=Path(sys.argv[2])

        legacy=SQLiteMarketStore.open(legacy_path)
        store=ShardedMarketStore(shard_root,legacy_store=legacy)
        shard=store.for_symbol('BTCUSDT')

        original=shard.upsert_candles
        calls={'count':0}

        def kill_after_first_commit(records):
            calls['count']+=1
            result=original(records)

            if calls['count']==1:
                # original() has returned, therefore the SQLite transaction for
                # this batch has already committed.  Exit immediately without
                # store.close(), legacy.close() or WAL checkpoint.
                os._exit(73)

            return result

        shard.upsert_candles=kill_after_first_commit

        store.migrate_legacy_candles(
            'BTCUSDT',
            batch_size=5,
        )

        os._exit(99)
    """)

    child=subprocess.run(
        [
            sys.executable,
            '-c',
            code,
            str(legacy_path),
            str(shard_root),
        ],
        capture_output=True,
        text=True,
    )

    assert child.returncode==73, (
        f'unexpected child return code {child.returncode}; '
        f'stdout={child.stdout!r}; stderr={child.stderr!r}'
    )

    # Fresh process state after the child disappeared abruptly.
    legacy=SQLiteMarketStore.open(legacy_path)
    recovered=ShardedMarketStore(
        shard_root,
        legacy_store=legacy,
    )

    record=recovered.manifest.get('BTCUSDT')
    assert record is not None
    assert record.state is ShardState.MIGRATING
    assert not recovered.manifest.ready('BTCUSDT')

    physical=recovered.for_symbol('BTCUSDT')

    # First batch was durably committed before os._exit().
    assert physical.coverage('BTCUSDT').count==5
    assert physical.integrity_check()

    # But routing must still expose the complete authoritative legacy source.
    assert recovered.coverage('BTCUSDT').count==25
    assert [
        row.open_time
        for row in recovered.iter_candles('BTCUSDT')
    ]==[
        i*60_000
        for i in range(25)
    ]

    # Resume using the already partially populated on-disk shard.
    recovered.migrate_legacy_candles(
        'BTCUSDT',
        batch_size=5,
    )

    record=recovered.manifest.get('BTCUSDT')

    assert record.state is ShardState.SHARD_READY
    assert record.rows_copied==25
    assert recovered.manifest.ready('BTCUSDT')

    # UPSERT semantics must prevent duplicates after replaying the first batch.
    assert physical.coverage('BTCUSDT').count==25
    assert recovered.coverage('BTCUSDT').count==25

    assert physical.coverage(
        'BTCUSDT'
    )==legacy.coverage(
        'BTCUSDT'
    )

    assert recovered._dataset_fingerprints(
        legacy,
        'BTCUSDT'
    )==recovered._dataset_fingerprints(
        physical,
        'BTCUSDT'
    )

    assert physical.integrity_check()

    # A second complete replay must also be harmless.
    recovered.migrate_legacy_candles(
        'BTCUSDT',
        batch_size=5,
    )

    assert physical.coverage('BTCUSDT').count==25
    assert recovered.manifest.ready('BTCUSDT')
    assert physical.integrity_check()

    recovered.close()
    legacy.close()


def test_os_hard_kill_before_shard_ready_commit_recovers_safely(tmp_path):
    """
    Kill the child process after the shard has been completely copied and
    validated but exactly when SHARD_READY is about to be persisted.

    The complete physical shard must remain non-authoritative after restart
    until a new migration pass validates it and durably promotes it.
    """
    from strattester.marketdata.sqlite_store import Candle
    from strattester.marketdata.sharded_store import ShardedMarketStore
    from strattester.marketdata.shard_manifest import ShardState

    legacy_path=tmp_path/'legacy.db'
    shard_root=tmp_path/'shards'

    legacy=SQLiteMarketStore.open(legacy_path)

    legacy.upsert_candles([
        Candle(
            'BTCUSDT',
            '1m',
            i*60_000,
            1,
            1.1,
            .9,
            1,
            1,
        )
        for i in range(25)
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

    legacy.close()

    code=textwrap.dedent(r"""
        import os
        import sys
        from pathlib import Path

        from strattester.marketdata.sqlite_store import SQLiteMarketStore
        from strattester.marketdata.sharded_store import ShardedMarketStore

        legacy_path=Path(sys.argv[1])
        shard_root=Path(sys.argv[2])

        legacy=SQLiteMarketStore.open(legacy_path)
        store=ShardedMarketStore(
            shard_root,
            legacy_store=legacy,
        )

        original_set=store.manifest.set

        def kill_at_ready(symbol,state,*args,**kwargs):
            value=getattr(state,'value',state)

            if value=='SHARD_READY':
                # migrate_legacy_candles reaches this only after candle
                # coverage, auxiliary fingerprints and SQLite integrity have
                # already passed validation.
                os._exit(74)

            return original_set(
                symbol,
                state,
                *args,
                **kwargs,
            )

        store.manifest.set=kill_at_ready

        store.migrate_legacy_candles(
            'BTCUSDT',
            batch_size=5,
        )

        os._exit(99)
    """)

    child=subprocess.run(
        [
            sys.executable,
            '-c',
            code,
            str(legacy_path),
            str(shard_root),
        ],
        capture_output=True,
        text=True,
    )

    assert child.returncode==74, (
        f'unexpected child return code {child.returncode}; '
        f'stdout={child.stdout!r}; stderr={child.stderr!r}'
    )

    # Open everything from scratch after abrupt child termination.
    legacy=SQLiteMarketStore.open(legacy_path)

    recovered=ShardedMarketStore(
        shard_root,
        legacy_store=legacy,
    )

    record=recovered.manifest.get('BTCUSDT')

    assert record is not None
    assert record.state is ShardState.MIGRATING
    assert not recovered.manifest.ready('BTCUSDT')

    physical=recovered.for_symbol('BTCUSDT')

    # Physical target is already complete.
    assert physical.coverage('BTCUSDT').count==25
    assert physical.coverage(
        'BTCUSDT',
        'funding',
    ).count==1

    assert physical.coverage(
        'BTCUSDT'
    )==legacy.coverage(
        'BTCUSDT'
    )

    assert recovered._dataset_fingerprints(
        legacy,
        'BTCUSDT'
    )==recovered._dataset_fingerprints(
        physical,
        'BTCUSDT'
    )

    assert physical.integrity_check()

    # Nevertheless the manifest is the authority boundary.  Until promotion
    # succeeds, routed reads must still resolve through legacy.
    assert recovered.coverage('BTCUSDT').count==25
    assert [
        row.open_time
        for row in recovered.iter_candles('BTCUSDT')
    ]==[
        i*60_000
        for i in range(25)
    ]

    # A fresh pass must be idempotent and complete the interrupted promotion.
    recovered.migrate_legacy_candles(
        'BTCUSDT',
        batch_size=5,
    )

    record=recovered.manifest.get('BTCUSDT')

    assert record.state is ShardState.SHARD_READY
    assert record.rows_copied==25
    assert recovered.manifest.ready('BTCUSDT')

    assert physical.coverage('BTCUSDT').count==25
    assert physical.coverage(
        'BTCUSDT',
        'funding',
    ).count==1

    assert recovered._dataset_fingerprints(
        legacy,
        'BTCUSDT'
    )==recovered._dataset_fingerprints(
        physical,
        'BTCUSDT'
    )

    assert physical.integrity_check()

    recovered.close()
    legacy.close()
