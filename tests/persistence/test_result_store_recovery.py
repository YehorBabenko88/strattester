import sqlite3
import pytest
from strattester.persistence.result_store import ResultStore

def test_result_write_is_atomic_and_survives_reopen(tmp_path):
    path=tmp_path/'results.db'
    s=ResultStore.open(path)
    s.put('r1','BTCUSDT','A','1',{'pnl':1})
    s.con.close()
    reopened=ResultStore.open(path)
    assert reopened.latest('BTCUSDT','A')['metrics']=={'pnl':1}
    assert reopened.integrity_check()
    reopened.close()

def test_failed_result_transaction_does_not_replace_previous_result(tmp_path):
    path=tmp_path/'results.db'
    s=ResultStore.open(path)
    s.put('r1','BTCUSDT','A','1',{'pnl':1},created_at=1)
    with pytest.raises(sqlite3.IntegrityError):
        with s.con:
            s.con.execute('INSERT INTO research_results(run_id,symbol,strategy_id,strategy_version,created_at,metrics) VALUES(?,?,?,?,?,?)',
                          (None,'BTCUSDT','A','1',2,'{}'))
    assert s.latest('BTCUSDT','A')['run_id']=='r1'
    assert s.integrity_check()
    s.close()


def test_reboot_never_auto_publishes_stale_staged_result(tmp_path):
    path=tmp_path/'results.db';s=ResultStore.open(path)
    s.stage('crash','r2','ETHUSDT','A','1',{'pnl':9},job_id='j',lease_token=4,node_generation=2)
    s.con.close()
    reopened=ResultStore.open(path)
    seen=[]
    outcome=reopened.recover_staged(lambda job,token,generation: seen.append((job,token,generation)) or False)
    assert outcome=={'promoted':0,'discarded':1}
    assert seen==[('j',4,2)] and reopened.latest('ETHUSDT','A') is None
    reopened.close()

def test_reboot_can_publish_stage_only_after_full_authority_revalidation(tmp_path):
    path=tmp_path/'results.db';s=ResultStore.open(path)
    s.stage('live','r3','SOLUSDT','A','1',{'pnl':2},job_id='j3',lease_token=8,node_generation=5)
    s.con.close();reopened=ResultStore.open(path)
    outcome=reopened.recover_staged(lambda job,token,generation:(job,token,generation)==('j3',8,5))
    assert outcome=={'promoted':1,'discarded':0}
    assert reopened.latest('SOLUSDT','A')['run_id']=='r3'
    reopened.close()

def test_legacy_staged_table_gets_generation_fence_columns(tmp_path):
    path=tmp_path/'legacy.db';con=sqlite3.connect(path)
    con.execute('''CREATE TABLE staged_research_results(
      stage_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,
      strategy_version TEXT NOT NULL,created_at REAL NOT NULL,metrics TEXT NOT NULL)''');con.commit();con.close()
    s=ResultStore.open(path)
    cols={r[1] for r in s.con.execute('PRAGMA table_info(staged_research_results)')}
    assert {'job_id','lease_token','node_generation'}<=cols
    s.close()


def test_staged_cleanup_is_age_bounded_and_never_deletes_published_results(tmp_path):
    s=ResultStore.open(tmp_path/'results.db')
    s.put('published','BTCUSDT','A','1',{'pnl':1},created_at=1)
    s.stage('old1','x1','X','A','1',{},created_at=1)
    s.stage('old2','x2','X','A','1',{},created_at=2)
    s.stage('new','x3','X','A','1',{},created_at=100)
    assert s.cleanup_staged(50,limit=1)==1
    assert s.cleanup_staged(50,limit=10)==1
    assert s.latest('BTCUSDT','A')['run_id']=='published'
    assert s.con.execute('SELECT stage_id FROM staged_research_results').fetchall()==[('new',)]
    s.close()
