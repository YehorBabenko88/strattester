from strattester.persistence.result_store import ResultStore

def test_result_store_persists_latest_strategy_result(tmp_path):
    s=ResultStore.open(tmp_path/'results.sqlite3')
    s.put('run-1','BTCUSDT','A','1',{'trades':10,'net_pnl':12.5})
    s.close()
    s=ResultStore.open(tmp_path/'results.sqlite3')
    row=s.latest('BTCUSDT','A')
    assert row['run_id']=='run-1' and row['metrics']['trades']==10 and row['metrics']['net_pnl']==12.5
    s.close()


def test_stale_lease_cannot_publish_staged_result(tmp_path):
    s=ResultStore.open(tmp_path/'results.sqlite3')
    s.stage('stage-old','run-old','BTCUSDT','A','1',{'net_pnl':99})
    assert s.promote('stage-old',lambda:False) is False
    assert s.latest('BTCUSDT','A') is None
    s.close()

def test_valid_lease_atomically_promotes_staged_result(tmp_path):
    s=ResultStore.open(tmp_path/'results.sqlite3')
    s.stage('stage-new','run-new','BTCUSDT','A','1',{'net_pnl':12.5})
    assert s.promote('stage-new',lambda:True) is True
    row=s.latest('BTCUSDT','A')
    assert row['run_id']=='run-new' and row['metrics']['net_pnl']==12.5
    assert s.promote('stage-new',lambda:True) is False
    s.close()


def test_older_fencing_generation_cannot_overwrite_newer_result(tmp_path):
    s=ResultStore.open(tmp_path/'results.sqlite3')
    s.stage('new','run-shared','BTCUSDT','A','1',{'net_pnl':20},created_at=200,job_id='job-1',lease_token=2)
    assert s.promote('new',lambda:True)
    s.stage('stale','run-shared','BTCUSDT','A','1',{'net_pnl':999},created_at=300,job_id='job-1',lease_token=1)
    assert s.promote('stale',lambda:True) is False
    row=s.latest('BTCUSDT','A')
    assert row['metrics']['net_pnl']==20
    s.close()

def test_result_store_migrates_legacy_schema_for_fencing(tmp_path):
    import sqlite3
    db=tmp_path/'legacy-results.sqlite3'
    con=sqlite3.connect(db)
    con.execute('''CREATE TABLE research_results(
        run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,strategy_version TEXT NOT NULL,
        created_at REAL NOT NULL,metrics TEXT NOT NULL,
        PRIMARY KEY(run_id,symbol,strategy_id,strategy_version))''')
    con.execute("INSERT INTO research_results VALUES('old','BTCUSDT','A','1',1,'{}')")
    con.commit(); con.close()
    s=ResultStore.open(db)
    assert s.latest('BTCUSDT','A')['run_id']=='old'
    s.stage('new','old','BTCUSDT','A','1',{'net_pnl':1},job_id='job',lease_token=1)
    assert s.promote('new',lambda:True)
    s.close()
