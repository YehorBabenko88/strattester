from strattester.runtime.worker import WorkerRuntime
from strattester.runtime.lifecycle import Lifecycle
from strattester.engine.jobs import Job,JobState
from strattester.engine.scheduler import Scheduler
from strattester.engine.resource_manager import ResourceSnapshot
from strattester.persistence.sqlite_state_store import SQLiteStateStore
import logging
GB=1024**3

def _picklable_cpu_executor(job):
    total=0
    for i in range(20000):
        total += (i*i) % 97
    return job.symbol,total
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


def test_auto_mode_can_use_process_pool_for_picklable_executor(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    jobs=[Job.new('backtest',symbol=f'S{i}',state=JobState.READY) for i in range(2)]
    for j in jobs: s.put_job(j)
    w=WorkerRuntime(
        s,Scheduler(s),_picklable_cpu_executor,Lifecycle(),logging.getLogger('test'),
        lambda:ResourceSnapshot(100*GB,100*GB,10*GB,0,4),
        execution_mode='auto')
    assert w._pool_kind()=='process'
    assert w.run_once()==2
    assert all(s.get_job(j.id).state is JobState.COMPLETE for j in jobs)
    s.close()


def test_permanent_failure_stops_after_max_attempts(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    job=Job.new('backtest',symbol='BROKEN',state=JobState.READY)
    s.put_job(job)
    def fail(j): raise RuntimeError('deterministic failure')
    w=WorkerRuntime(
        s,Scheduler(s),fail,Lifecycle(),logging.getLogger('test'),
        lambda:ResourceSnapshot(100*GB,100*GB,10*GB,0,4),
        execution_mode='thread',max_attempts=3)
    assert w.run_once()==1
    assert s.get_job(job.id).state is JobState.RETRYABLE
    assert w.run_once()==1
    assert s.get_job(job.id).state is JobState.RETRYABLE
    assert w.run_once()==1
    failed=s.get_job(job.id)
    assert failed.state is JobState.FAILED
    assert failed.attempts==3
    assert w.run_once()==0
    s.close()

def test_broken_job_does_not_block_other_symbols(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    bad=Job.new('backtest',symbol='BAD',state=JobState.READY)
    good=Job.new('backtest',symbol='GOOD',state=JobState.READY)
    s.put_job(bad); s.put_job(good)
    def execute(j):
        if j.symbol=='BAD': raise OSError('simulated local database failure')
        return 'ok'
    w=WorkerRuntime(
        s,Scheduler(s),execute,Lifecycle(),logging.getLogger('test'),
        lambda:ResourceSnapshot(100*GB,100*GB,10*GB,0,4),
        execution_mode='thread',max_attempts=1)
    assert w.run_once()==2
    assert s.get_job(bad.id).state is JobState.FAILED
    assert s.get_job(good.id).state is JobState.COMPLETE
    s.close()


def test_cluster_worker_refuses_new_work_when_control_plane_heartbeat_fails(tmp_path):
    base=SQLiteStateStore.open(tmp_path/'s.db')
    job=Job.new('backtest',symbol='BTCUSDT',target_node='PC1',state=JobState.READY)
    base.put_job(job)
    class BrokenControlPlane:
        def heartbeat_node(self,*a,**k): raise ConnectionError('postgres unavailable')
        def live_nodes(self,*a,**k): raise ConnectionError('postgres unavailable')
        def list_jobs(self): return base.list_jobs()
        def claim_ready_jobs(self,*a,**k): raise AssertionError('must not claim while control plane is down')
        def put_job(self,j): return base.put_job(j)
    state=BrokenControlPlane()
    w=WorkerRuntime(
        state,Scheduler(state),lambda j:None,Lifecycle(),logging.getLogger('test'),
        lambda:ResourceSnapshot(100*GB,100*GB,10*GB,0,4),
        node_id='PC1',execution_mode='thread')
    assert w.run_once()==0
    assert base.get_job(job.id).state is JobState.READY
    assert not w.control_plane_healthy
    base.close()


def test_cluster_worker_recovers_after_control_plane_returns(tmp_path):
    base=SQLiteStateStore.open(tmp_path/'s.db')
    job=Job.new('backtest',symbol='BTCUSDT',target_node='PC1',state=JobState.READY)
    base.put_job(job)
    class FlakyControlPlane:
        def __init__(self): self.up=False
        def heartbeat_node(self,*a,**k):
            if not self.up: raise ConnectionError('postgres unavailable')
        def reconnect(self): self.up=True; return True
        def live_nodes(self,*a,**k): return ('PC1',)
        def list_jobs(self): return base.list_jobs()
        def put_job(self,j): return base.put_job(j)
        def claim_ready_jobs(self,*a,**k): return base.claim_ready_jobs(*a,**k)
        def transition_claimed(self,*a,**k): return base.transition_claimed(*a,**k)
        def get_job(self,*a,**k): return base.get_job(*a,**k)
        def renew_lease(self,*a,**k): return base.renew_lease(*a,**k)
    state=FlakyControlPlane()
    w=WorkerRuntime(
        state,Scheduler(state),lambda j:None,Lifecycle(),logging.getLogger('test'),
        lambda:ResourceSnapshot(100*GB,100*GB,10*GB,0,4),
        node_id='PC1',execution_mode='thread')
    assert w.run_once()==0
    assert base.get_job(job.id).state is JobState.READY
    assert w.run_once()==1
    assert base.get_job(job.id).state is JobState.COMPLETE
    assert w.control_plane_healthy
    base.close()


def test_executor_crash_never_marks_job_complete(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'s.db')
    job=Job.new('backtest',symbol='BTCUSDT',state=JobState.READY)
    s.put_job(job)
    def crash(j): raise SystemExit(17)
    w=WorkerRuntime(
        s,Scheduler(s),crash,Lifecycle(),logging.getLogger('test'),
        lambda:ResourceSnapshot(100*GB,100*GB,10*GB,0,4),
        execution_mode='thread',max_attempts=3)
    assert w.run_once()==1
    after=s.get_job(job.id)
    assert after.state is JobState.RETRYABLE
    assert after.state is not JobState.COMPLETE
    assert after.lease_owner is None
    s.close()


def test_worker_close_releases_owned_resources_once(tmp_path):
    class Resource:
        def __init__(self): self.closed=0
        def close(self): self.closed+=1
    resource=Resource()
    state=SQLiteStateStore.open(tmp_path/'state.db')
    runtime=WorkerRuntime(state,Scheduler(state),lambda job:None,Lifecycle(),
        build_logger(tmp_path/'worker.jsonl','test.worker.close'),
        lambda:ResourceSnapshot(8*1024**3,6*1024**3,50*1024**3,10,4),
        resources=[resource])
    runtime.close()
    runtime.close()
    assert resource.closed==1
    state.close()
