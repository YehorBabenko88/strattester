from strattester.persistence.result_store import ResultStore

def test_result_store_persists_latest_strategy_result(tmp_path):
    s=ResultStore.open(tmp_path/'results.sqlite3')
    s.put('run-1','BTCUSDT','A','1',{'trades':10,'net_pnl':12.5})
    s.close()
    s=ResultStore.open(tmp_path/'results.sqlite3')
    row=s.latest('BTCUSDT','A')
    assert row['run_id']=='run-1' and row['metrics']['trades']==10 and row['metrics']['net_pnl']==12.5
    s.close()
