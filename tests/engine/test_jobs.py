from strattester.engine.jobs import Job,JobState
from strattester.persistence.sqlite_state_store import SQLiteStateStore
def test_stale_running_job_becomes_retryable(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    j=Job.new('strategy',state=JobState.RUNNING,lease_owner='node',lease_until=10)
    s.put_job(j); r=s.get_job(j.id).recover_stale(11)
    assert r.state==JobState.RETRYABLE and r.lease_owner is None
    s.close()
def test_worker_disappearance_does_not_mean_complete():
    j=Job.new('strategy',state=JobState.RUNNING)
    assert j.recover_stale(100).state==JobState.RUNNING
