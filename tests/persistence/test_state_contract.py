from strattester.engine.jobs import Job,JobState
from strattester.persistence.sqlite_state_store import SQLiteStateStore
from strattester.persistence.migrate_state import copy_jobs
def test_local_state_contract_and_copy(tmp_path):
    a=SQLiteStateStore.open(tmp_path/'a.db'); b=SQLiteStateStore.open(tmp_path/'b.db')
    j=Job.new('sync',symbol='BTCUSDT',state=JobState.READY); a.put_job(j)
    assert a.get_job(j.id)==j
    assert copy_jobs(a,b)==1 and b.get_job(j.id)==j
    a.close();b.close()
