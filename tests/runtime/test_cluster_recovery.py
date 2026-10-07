from strattester.engine.jobs import Job,JobState
from strattester.persistence.sqlite_state_store import SQLiteStateStore
from strattester.runtime.cluster_recovery import ClusterRecovery

class ClusterState:
    def __init__(self,inner,live): self.inner=inner; self.live=tuple(live)
    def live_nodes(self,stale_after=30,now=None): return self.live
    def list_jobs(self): return self.inner.list_jobs()
    def put_job(self,j): return self.inner.put_job(j)
    def compare_and_swap_job(self,expected,replacement): return self.inner.compare_and_swap_job(expected,replacement)

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


def test_recovery_is_idempotent_after_first_move(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    job=Job.new('sync',symbol='BTCUSDT',target_node='PC1',resource_key='market:PC1:BTCUSDT',
                state=JobState.RETRYABLE)
    s.put_job(job)
    recovery=ClusterRecovery(ClusterState(s,('PC2',)))
    first=recovery.reconcile(now=100)
    second=recovery.reconcile(now=101)
    assert first.reassigned==(job.id,)
    assert second.reassigned==()
    moved=s.get_job(job.id)
    assert moved.target_node=='PC2'
    assert moved.resource_key=='market:PC2:BTCUSDT'
    s.close()


def test_competing_recovery_cas_allows_only_first_snapshot_to_commit(tmp_path):
    path=tmp_path/'shared-state.db'
    a=SQLiteStateStore.open(path)
    b=SQLiteStateStore.open(path)
    job=Job.new('sync',symbol='BTCUSDT',target_node='PC1',resource_key='market:PC1:BTCUSDT',
                state=JobState.RUNNING,lease_owner='dead-worker',lease_until=99,lease_token=7)
    a.put_job(job)
    snapshot_a=a.get_job(job.id)
    snapshot_b=b.get_job(job.id)
    from strattester.engine.distribution import reassign_unavailable
    moved_a=reassign_unavailable(snapshot_a.recover_stale(100),('PC2','PC3'))
    moved_b=reassign_unavailable(snapshot_b.recover_stale(100),('PC2','PC3'))
    assert a.compare_and_swap_job(snapshot_a,moved_a) is True
    assert b.compare_and_swap_job(snapshot_b,moved_b) is False
    final=a.get_job(job.id)
    assert final==moved_a
    assert final.lease_token==7
    a.close(); b.close()


def test_reassigned_expired_job_gets_new_fencing_token_when_reclaimed(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    job=Job.new('sync',symbol='BTCUSDT',target_node='PC1',state=JobState.RUNNING,
                lease_owner='old-worker',lease_until=9,lease_token=7)
    s.put_job(job)
    ClusterRecovery(ClusterState(s,('PC2',))).reconcile(now=10)
    moved=s.get_job(job.id)
    assert moved.state is JobState.RETRYABLE and moved.lease_token==7
    claimed=s.claim_ready_jobs('new-worker',limit=1,now=11,lease_seconds=30,
                               job_ids=[job.id],node_id='PC2')
    assert len(claimed)==1 and claimed[0].lease_token==8
    assert claimed[0].lease_owner=='new-worker'
    assert s.transition_claimed(job.id,'old-worker',7,JobState.COMPLETE) is False
    s.close()
