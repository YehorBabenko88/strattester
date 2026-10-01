from strattester.engine.jobs import Job,JobState
from strattester.engine.scheduler import Scheduler
from strattester.engine.resource_manager import ResourceSnapshot
from strattester.persistence.sqlite_state_store import SQLiteStateStore
def test_scheduler_recovers_stale_and_limits_jobs(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    s.put_job(Job.new('x',state=JobState.RUNNING,lease_until=1))
    sch=Scheduler(s); recovered=sch.recover_stale_jobs(2)
    assert recovered[0].state==JobState.RETRYABLE
    jobs=sch.ready_jobs(ResourceSnapshot(100,30,10*1024**3))
    assert len(jobs)==1
    s.close()
