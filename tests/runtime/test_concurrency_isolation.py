from strattester.engine.jobs import Job,JobState
from strattester.persistence.sqlite_state_store import SQLiteStateStore

def test_two_workers_cannot_claim_same_job(tmp_path):
    p=tmp_path/'state.db'
    a=SQLiteStateStore.open(p); b=SQLiteStateStore.open(p)
    job=Job.new('backtest',symbol='BTCUSDT',strategy_id='A',state=JobState.READY)
    a.put_job(job)
    ca=a.claim_ready_jobs('worker-a',limit=1,now=100,lease_seconds=60)
    cb=b.claim_ready_jobs('worker-b',limit=1,now=100,lease_seconds=60)
    assert [x.id for x in ca]==[job.id]
    assert cb==[]
    assert b.get_job(job.id).lease_owner=='worker-a'
    a.close(); b.close()

def test_exclusive_resource_prevents_competing_sync_jobs(tmp_path):
    p=tmp_path/'state.db'; s=SQLiteStateStore.open(p)
    a=Job.new('sync',symbol='BTCUSDT',resource_key='market:BTCUSDT',state=JobState.READY)
    b=Job.new('sync',symbol='BTCUSDT',resource_key='market:BTCUSDT',state=JobState.READY)
    s.put_job(a); s.put_job(b)
    first=s.claim_ready_jobs('w1',limit=2,now=100,lease_seconds=60)
    assert len(first)==1
    second=s.claim_ready_jobs('w2',limit=2,now=100,lease_seconds=60)
    assert second==[]
    s.close()

def test_different_strategy_backtests_do_not_share_trade_state(tmp_path):
    from strattester.strategies.builtin.legacy_grid import MinuteCandle,run_legacy_suite
    rows=[
      MinuteCandle(0,100,110,90,100),
      MinuteCandle(3_600_000,100,101,99,100),
      MinuteCandle(3_660_000,100,111,99,110),
    ]
    together=run_legacy_suite(rows,('HIGH_BASE','HIGH_SHORT'))
    high_only=run_legacy_suite(rows,('HIGH_BASE',))
    short_only=run_legacy_suite(rows,('HIGH_SHORT',))
    assert together['HIGH_BASE']==high_only['HIGH_BASE']
    assert together['HIGH_SHORT']==short_only['HIGH_SHORT']
