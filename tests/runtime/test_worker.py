from strattester.runtime.worker import WorkerRuntime
from strattester.runtime.lifecycle import Lifecycle
from strattester.engine.jobs import Job,JobState
from strattester.engine.scheduler import Scheduler
from strattester.engine.resource_manager import ResourceSnapshot
from strattester.persistence.sqlite_state_store import SQLiteStateStore
import logging
GB=1024**3
def test_one_failure_is_retryable_and_next_job_completes(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    a=Job.new('x',symbol='BAD',state=JobState.READY); b=Job.new('x',symbol='GOOD',state=JobState.READY)
    s.put_job(a);s.put_job(b)
    def execute(j):
        if j.symbol=='BAD': raise RuntimeError('boom')
    w=WorkerRuntime(s,Scheduler(s),execute,Lifecycle(),logging.getLogger('test'),lambda:ResourceSnapshot(100*GB,100*GB,10*GB))
    assert w.run_once()==2
    assert s.get_job(a.id).state==JobState.RETRYABLE
    assert s.get_job(b.id).state==JobState.COMPLETE
    s.close()

def test_worker_claims_only_jobs_selected_by_scheduler(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    a=Job.new('x',symbol='A',state=JobState.READY); b=Job.new('x',symbol='B',state=JobState.READY)
    s.put_job(a); s.put_job(b)
    class OnlyB:
        def ready_jobs(self,snapshot): return [b]
    seen=[]
    w=WorkerRuntime(s,OnlyB(),lambda j:seen.append(j.symbol),Lifecycle(),logging.getLogger('test'),lambda:ResourceSnapshot(100*GB,100*GB,10*GB))
    assert w.run_once()==1
    assert seen==['B']
    assert s.get_job(a.id).state==JobState.READY


def test_retryable_failure_releases_worker_lease(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    a=Job.new('x',symbol='BAD',resource_key='market:BTCUSDT',state=JobState.READY)
    s.put_job(a)
    w=WorkerRuntime(
        s,Scheduler(s),lambda j:(_ for _ in ()).throw(RuntimeError('boom')),
        Lifecycle(),logging.getLogger('test'),lambda:ResourceSnapshot(100*GB,100*GB,10*GB))
    assert w.run_once()==1
    failed=s.get_job(a.id)
    assert failed.state==JobState.RETRYABLE
    assert failed.lease_owner is None and failed.lease_until is None
    s.close()


def test_worker_runs_independent_jobs_concurrently(tmp_path):
    import threading,time
    s=SQLiteStateStore.open(tmp_path/'s.db')
    jobs=[Job.new('x',symbol=f'S{i}',state=JobState.READY) for i in range(4)]
    for j in jobs: s.put_job(j)
    lock=threading.Lock(); active=0; peak=0
    def execute(j):
        nonlocal active,peak
        with lock:
            active+=1; peak=max(peak,active)
        time.sleep(0.05)
        with lock: active-=1
    w=WorkerRuntime(
        s,Scheduler(s),execute,Lifecycle(),logging.getLogger('test'),
        lambda:ResourceSnapshot(100*GB,100*GB,10*GB,0,8),
        execution_mode='thread')
    assert w.run_once()==4
    assert peak>=2
    assert all(s.get_job(j.id).state is JobState.COMPLETE for j in jobs)
    s.close()
