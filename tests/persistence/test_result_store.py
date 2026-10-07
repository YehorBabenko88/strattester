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
