from strattester.engine.jobs import Job,JobState
from strattester.persistence.sqlite_state_store import SQLiteStateStore
from strattester.runtime.cluster_recovery import ClusterRecovery

class ClusterState:
    def __init__(self,inner,live): self.inner=inner; self.live=tuple(live)
    def live_nodes(self,stale_after=30,now=None): return self.live
    def list_jobs(self): return self.inner.list_jobs()
    def put_job(self,j): return self.inner.put_job(j)

def test_expired_job_on_dead_node_moves_and_rebinds_writer_lock(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    job=Job.new('sync',symbol='BTCUSDT',target_node='PC1',resource_key='market:PC1:BTCUSDT',
                state=JobState.RUNNING,lease_owner='old',lease_until=99,lease_token=3)
    s.put_job(job)
    report=ClusterRecovery(ClusterState(s,('PC2','PC3'))).reconcile(now=100)
    moved=s.get_job(job.id)
    assert job.id in report.reassigned
    assert moved.target_node in ('PC2','PC3')
    assert moved.resource_key==f'market:{moved.target_node}:BTCUSDT'
    assert moved.state is JobState.RETRYABLE
    assert moved.lease_owner is None and moved.lease_until is None
    s.close()

def test_live_lease_on_dead_heartbeat_node_is_deferred_until_lease_expires(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    job=Job.new('backtest',symbol='ETHUSDT',target_node='PC1',state=JobState.RUNNING,
                lease_owner='old',lease_until=110,lease_token=4)
    s.put_job(job)
    report=ClusterRecovery(ClusterState(s,('PC2',))).reconcile(now=100)
    assert job.id in report.deferred
    assert s.get_job(job.id).target_node=='PC1'
    report=ClusterRecovery(ClusterState(s,('PC2',))).reconcile(now=111)
    assert job.id in report.reassigned
    assert s.get_job(job.id).target_node=='PC2'
    s.close()

def test_completed_job_is_never_reassigned(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    job=Job.new('backtest',symbol='SOLUSDT',target_node='PC1',state=JobState.COMPLETE)
    s.put_job(job)
    report=ClusterRecovery(ClusterState(s,('PC2',))).reconcile(now=100)
    assert report.reassigned==()
    assert s.get_job(job.id).target_node=='PC1'
    s.close()
