import json
import sqlite3
from types import SimpleNamespace
import pytest
from strattester.marketdata.sqlite_store import Candle
from strattester.persistence.result_store import ResultStore
from strattester.research.provenance import execute_owned, validate
from strattester.strategies.base import StrategyDefinition,DataRequirement
from strattester.readonly_api import ReadOnlyResultsApp

class Strategy:
    def run(self,candles,checkpoint=None):
        return {'sum':sum(c.close for c in candles)}

D=StrategyDefinition('test','1',(DataRequirement('candles',('1m',)),),Strategy)
META=dict(source_identity='synthetic:fixture',market_type='linear',producer_identity='synthetic:owner',source_revision='a'*40,model={'kind':'synthetic','version':'1'},execution_assumptions={'fees':0,'slippage':0,'execution':'none'})

def setup(tmp_path):
    rows=[Candle('BTCUSDT','1m',t,1,2,1,2,1) for t in (0,60000)]
    store=SimpleNamespace(iter_candles=lambda *a,**k:iter(rows))
    results=ResultStore.open(tmp_path/'results.db')
    return rows,store,results

def request(app,path):
    return json.loads(b''.join(app({'PATH_INFO':path,'REQUEST_METHOD':'GET'},lambda *a:None)))

def test_real_producer_receipt_api_and_immutable(tmp_path):
    rows,store,results=setup(tmp_path)
    execute_owned(D,store,'BTCUSDT',0,60000,results,**META)
    record=json.loads(results.con.execute('SELECT record FROM owned_runs').fetchone()[0])
    assert validate(record) is None
    assert record['metrics']=={'sum':4}
    assert request(ReadOnlyResultsApp(results.path),'/internal/v1/runs')['reason']=='SOURCE_TRUST_UNCONFIGURED'
    app=ReadOnlyResultsApp(results.path,trusted_sources=[('synthetic:owner','a'*40,'synthetic:fixture')],trusted_receipts=[('synthetic:owner','a'*40,record['run_id'],record['completion_receipt'])])
    assert request(app,'/internal/v1/runs')['runs']==[record]
    assert request(app,f"/internal/v1/runs/{record['run_id']}/metrics")['mode']=='HISTORICAL'
    with pytest.raises(sqlite3.IntegrityError): results.con.execute("UPDATE owned_runs SET record='{}'")
    with pytest.raises(sqlite3.IntegrityError): results.con.execute('DELETE FROM owned_runs')
    with pytest.raises(sqlite3.IntegrityError): results.con.execute("INSERT OR REPLACE INTO owned_runs VALUES(?,'RUNNING',NULL)",(record['run_id'],))
    results.con.rollback()
    results.close()

def test_gap_cancel_duplicate_and_rerun(tmp_path):
    rows,store,results=setup(tmp_path)
    with pytest.raises(RuntimeError,match='CANCELLED'): execute_owned(D,store,'BTCUSDT',0,60000,results,cancelled=lambda:True,**META)
    assert results.con.execute('SELECT state FROM owned_runs').fetchone()[0]=='ABORTED'
    for _ in range(2): execute_owned(D,store,'BTCUSDT',0,60000,results,**META)
    assert results.con.execute("SELECT count(DISTINCT run_id) FROM owned_runs WHERE state='COMPLETE'").fetchone()[0]==2
    rows.append(rows[0])
    with pytest.raises(ValueError,match='GAP'): execute_owned(D,store,'BTCUSDT',0,60000,results,**META)
    results.close()

def test_receipt_tamper_restart_and_fencing(tmp_path):
    rows,store,results=setup(tmp_path)
    with pytest.raises(RuntimeError,match='PUBLICATION_FENCED'): execute_owned(D,store,'BTCUSDT',0,60000,results,lease_validator=lambda:False,**META)
    results.begin_owned('crash-left')
    results.close()
    results=ResultStore.open(tmp_path/'results.db')
    assert request(ReadOnlyResultsApp(results.path,trusted_sources=[('x','y','z')]),'/internal/v1/runs/crash-left/metrics')['reason']=='RUN_INCOMPLETE'
    execute_owned(D,store,'BTCUSDT',0,60000,results,**META)
    record=json.loads(results.con.execute("SELECT record FROM owned_runs WHERE state='COMPLETE'").fetchone()[0])
    record['metrics']['sum']=999
    assert validate(record)=='RECEIPT_INVALID'
    record['api_version']['major']=2
    assert validate(record)=='VERSION_UNSUPPORTED'
    results.close()

def test_runner_multi_dataset_uses_frozen_snapshot(tmp_path):
    from strattester.research.runner import ResearchRunner
    from strattester.marketdata.sqlite_store import SQLiteMarketStore
    market=SQLiteMarketStore.open(tmp_path/'market.db')
    market.upsert_candles([Candle('BTCUSDT','1m',t,1,2,1,2,1) for t in (0,60000)])
    market.upsert_price_klines('mark_price','BTCUSDT',[[0,1,2,1,2],[60000,1,2,1,2]])
    class Multi:
        def run_context(self,context,checkpoint=None):
            market.upsert_candles([Candle('BTCUSDT','1m',0,1,99,1,99,1)])
            return {'count':context.coverage('mark_price').count,'sum':sum(c.close for c in context.candles())}
    definition=StrategyDefinition('multi','1',(DataRequirement('candles',('1m',)),DataRequirement('mark_price',('1m',))),Multi)
    results=ResultStore.open(tmp_path/'results.db')
    runner=ResearchRunner(market,object())
    runner._sync_definition=lambda *args: None
    runner.run(definition,{'symbol':'BTCUSDT'},start_ms=0,end_ms=60000,result_store=results,provenance=META)
    record=json.loads(results.con.execute('SELECT record FROM owned_runs').fetchone()[0])
    assert record['metrics']=={'count':2,'sum':4}
    assert len(record['input_snapshot'])==2
    assert validate(record) is None
    results.close();market.close()

@pytest.mark.parametrize('mutate',[
    lambda r:r['api_version'].update(major=True),
    lambda r:r.update(producer='grid'),
    lambda r:r.update(producer_epoch='not-uuid'),
    lambda r:r.update(completed_at_ms=0),
    lambda r:r.update(model='unknown'),
    lambda r:r['dataset'].update(coverage='PARTIAL'),
    lambda r:r['input_snapshot'][0]['rows'].pop(),
])
def test_self_rehashed_malformed_records_fail(tmp_path,mutate):
    from strattester.research.provenance import digest
    rows,store,results=setup(tmp_path)
    execute_owned(D,store,'BTCUSDT',0,60000,results,**META)
    record=json.loads(results.con.execute('SELECT record FROM owned_runs').fetchone()[0])
    mutate(record)
    record['completion_receipt']=digest({k:v for k,v in record.items() if k!='completion_receipt'})
    assert validate(record) is not None
    results.close()

def test_metadata_cannot_admit_relabelled_record(tmp_path):
    rows,store,results=setup(tmp_path)
    execute_owned(D,store,'BTCUSDT',0,60000,results,**META)
    app=ReadOnlyResultsApp(results.path,trusted_sources=[('synthetic:owner','a'*40,'synthetic:fixture')])
    assert request(app,'/internal/v1/runs')['reason']=='SOURCE_RECEIPT_UNTRUSTED'
    with pytest.raises(ValueError,match='CHECKPOINT_BINDING_UNAVAILABLE'):
        execute_owned(D,store,'BTCUSDT',0,60000,results,checkpoint={},**META)
    with pytest.raises(ValueError,match='PARAMETERS_ADAPTER_UNAVAILABLE'):
        execute_owned(D,store,'BTCUSDT',0,60000,results,parameters={'period':2},**META)
    results.close()

def test_bounded_artifact_query(tmp_path):
    rows,store,results=setup(tmp_path)
    results.con.execute("INSERT INTO owned_runs VALUES('large','COMPLETE',?)",(' '*900001,))
    results.con.commit()
    app=ReadOnlyResultsApp(results.path,trusted_sources=[('x','y','z')])
    assert request(app,'/internal/v1/runs')['reason']=='ARTIFACT_SIZE_UNAVAILABLE'
    results.close()
