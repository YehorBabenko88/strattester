from strattester.engine.jobs import Job,JobState
from strattester.persistence.sqlite_state_store import SQLiteStateStore
from strattester.persistence.migrate_state import copy_jobs
def test_local_state_contract_and_copy(tmp_path):
    a=SQLiteStateStore.open(tmp_path/'a.db'); b=SQLiteStateStore.open(tmp_path/'b.db')
    j=Job.new('sync',symbol='BTCUSDT',state=JobState.READY); a.put_job(j)
    assert a.get_job(j.id)==j
    assert copy_jobs(a,b)==1 and b.get_job(j.id)==j
    a.close();b.close()


def test_lease_valid_requires_exact_owner_token_active_state_and_time(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'lease-valid.db')
    job=Job.new('backtest',symbol='BTCUSDT',state=JobState.READY)
    s.put_job(job)
    claimed=s.claim_ready_jobs('worker-a',1,now=100,lease_seconds=10)[0]
    assert s.lease_valid(job.id,'worker-a',claimed.lease_token,now=105)
    assert not s.lease_valid(job.id,'worker-b',claimed.lease_token,now=105)
    assert not s.lease_valid(job.id,'worker-a',claimed.lease_token+1,now=105)
    assert not s.lease_valid(job.id,'worker-a',claimed.lease_token,now=111)
    s.close()
