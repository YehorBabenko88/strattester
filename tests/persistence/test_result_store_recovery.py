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
            s.con.execute('INSERT INTO research_results VALUES(?,?,?,?,?,?)',
                          (None,'BTCUSDT','A','1',2,'{}'))
    assert s.latest('BTCUSDT','A')['run_id']=='r1'
    assert s.integrity_check()
    s.close()
