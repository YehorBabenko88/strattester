from strattester.runtime.worker import WorkerRuntime
from strattester.runtime.lifecycle import Lifecycle
from strattester.engine.jobs import Job,JobState
from strattester.engine.scheduler import Scheduler
from strattester.engine.resource_manager import ResourceSnapshot
from strattester.persistence.sqlite_state_store import SQLiteStateStore
import logging
def test_one_failure_is_retryable_and_next_job_completes(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    a=Job.new('x',symbol='BAD',state=JobState.READY); b=Job.new('x',symbol='GOOD',state=JobState.READY)
    s.put_job(a);s.put_job(b)
    def execute(j):
        if j.symbol=='BAD': raise RuntimeError('boom')
    w=WorkerRuntime(s,Scheduler(s),execute,Lifecycle(),logging.getLogger('test'),lambda:ResourceSnapshot(100,100,10*1024**3))
    assert w.run_once()==2
    assert s.get_job(a.id).state==JobState.RETRYABLE
    assert s.get_job(b.id).state==JobState.COMPLETE
    s.close()
