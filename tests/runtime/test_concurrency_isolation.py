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

from strattester.engine.jobs import Job,JobState
from strattester.persistence.sqlite_state_store import SQLiteStateStore

def test_same_market_writer_is_exclusive_but_backtests_remain_parallel(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    sync1=Job.new('sync',symbol='BTCUSDT',resource_key='market:BTCUSDT',state=JobState.READY)
    sync2=Job.new('sync',symbol='BTCUSDT',resource_key='market:BTCUSDT',state=JobState.READY)
    a=Job.new('backtest',symbol='BTCUSDT',strategy_id='A',state=JobState.READY)
    b=Job.new('backtest',symbol='BTCUSDT',strategy_id='B',state=JobState.READY)
    for j in (sync1,sync2,a,b): s.put_job(j)
    claimed=s.claim_ready_jobs('w1',limit=4,now=100,lease_seconds=60)
    ids={x.id for x in claimed}
    assert a.id in ids and b.id in ids
    assert len({sync1.id,sync2.id}&ids)==1
    s.close()

def test_expired_writer_lease_releases_resource(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    old=Job.new('sync',symbol='BTCUSDT',resource_key='market:BTCUSDT',state=JobState.RUNNING,
                lease_owner='dead',lease_until=99)
    new=Job.new('sync',symbol='BTCUSDT',resource_key='market:BTCUSDT',state=JobState.READY)
    s.put_job(old); s.put_job(new)
    claimed=s.claim_ready_jobs('w2',limit=2,now=100,lease_seconds=60)
    sync_claims=[x for x in claimed if x.resource_key=='market:BTCUSDT']
    assert len(sync_claims)==1
    assert sync_claims[0].id in (old.id,new.id)
    # The stale job may itself be retried first; the invariant is that the
    # resource is released and exactly one writer is leased, never two.
    states={s.get_job(old.id).state,s.get_job(new.id).state}
    assert JobState.LEASED in states
    s.close()


def test_stale_worker_cannot_complete_after_takeover(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    job=Job.new('backtest',symbol='BTCUSDT',state=JobState.READY)
    s.put_job(job)
    first=s.claim_ready_jobs('w1',limit=1,now=100,lease_seconds=10)[0]
    assert s.transition_claimed(first.id,'w1',first.lease_token,JobState.RUNNING)
    second=s.claim_ready_jobs('w2',limit=1,now=111,lease_seconds=10)[0]
    assert second.lease_token==first.lease_token+1
    assert not s.transition_claimed(first.id,'w1',first.lease_token,JobState.COMPLETE,
                                    lease_owner=None,lease_until=None)
    assert s.transition_claimed(second.id,'w2',second.lease_token,JobState.COMPLETE,
                                lease_owner=None,lease_until=None)
    assert s.get_job(job.id).state is JobState.COMPLETE
    s.close()

def test_live_lease_renewal_prevents_takeover(tmp_path):
    p=tmp_path/'state.db'
    a=SQLiteStateStore.open(p); b=SQLiteStateStore.open(p)
    job=Job.new('backtest',symbol='BTCUSDT',state=JobState.READY)
    a.put_job(job)
    first=a.claim_ready_jobs('w1',limit=1,now=100,lease_seconds=10)[0]
    assert a.transition_claimed(first.id,'w1',first.lease_token,JobState.RUNNING)
    assert a.renew_lease(first.id,'w1',first.lease_token,lease_seconds=10,now=108)
    assert b.claim_ready_jobs('w2',limit=1,now=111,lease_seconds=10)==[]
    a.close(); b.close()
