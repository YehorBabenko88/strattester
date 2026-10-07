from strattester.engine.jobs import Job,JobState
from strattester.engine.scheduler import Scheduler
from strattester.engine.resource_manager import ResourceSnapshot
from strattester.persistence.sqlite_state_store import SQLiteStateStore

GB=1024**3

def test_node_filter_happens_before_parallel_slot_limit(tmp_path):
    s=SQLiteStateStore.open(tmp_path/'state.db')
    for i in range(10):
        s.put_job(Job.new('backtest',symbol=f'A{i}',target_node='PC1',state=JobState.READY))
    mine=[Job.new('backtest',symbol=f'B{i}',target_node='PC2',state=JobState.READY) for i in range(3)]
    for j in mine: s.put_job(j)
    snap=ResourceSnapshot(64*GB,48*GB,100*GB,0,8)
    selected=Scheduler(s).ready_jobs(snap,node_id='PC2')
    assert {j.id for j in selected}=={j.id for j in mine}
    s.close()
