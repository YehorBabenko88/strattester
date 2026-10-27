"""Independent three-instrument/two-timeframe CLI experiment fixtures."""
from dataclasses import asdict
from hashlib import sha256
import json
import subprocess
import sys
import pytest
from strattester.research.financial_contract import Bar,Instrument,Snapshot
from strattester.research.financial_experiment import Example
from strattester.research.financial_structural_model import StructuralConfig
from strattester.research.financial_snapshot import canonical_bytes

def source(tmp_path):
    examples=[]
    for origin in (360,720,1080,1440,1800,2160,2520,2880,3240):
        for tf in (60,120):
            bars=[]
            for i,symbol in enumerate(('BTCUSDT','ETHUSDT','SOLUSDT')):
                for j in range(3):
                    t=origin-(3-j)*tf
                    bars.append(Bar(Instrument('bybit','linear',symbol),tf,t,t+tf,t+tf-1,t+tf,t+tf,origin,100.+j+i+origin/10000,'VERIFIED',True,True,1,'public-software-fixture','a'*40))
            snapshot=Snapshot(tuple(bars),origin,'synthetic-experiment',('public-software-fixture',))
            for i,symbol in enumerate(('BTCUSDT','ETHUSDT','SOLUSDT')):
                examples.append(asdict(Example(snapshot,Instrument('bybit','linear',symbol),tf,origin+120,.001*(i-1))))
    payload=dict(version=1,scope='SYNTHETIC_ENGINEERING_ONLY',examples=examples,config=asdict(StructuralConfig(recycles=0)),train_end=1200,validation_end=2400,test_end=3400,holdout_symbols=['SOLUSDT'],steps=1,seed=12,fee_bps=2.,slippage_bps=1.,embargo_ns=0)
    path=tmp_path/'experiment.json';data=canonical_bytes(payload);path.write_bytes(data)
    return path,sha256(data).hexdigest(),payload

def test_cli_experiment_trains_reloads_forecasts_and_backtests_three_instruments_two_timeframes(tmp_path):
    path,pin,payload=source(tmp_path);out=tmp_path/'output'
    command=[sys.executable,'-m','strattester.research_cli','experiment','--source',str(path),'--source-sha256',pin,'--output',str(out),'--enable-research']
    completed=subprocess.run(command,capture_output=True,text=True,timeout=60)
    assert completed.returncode==0,completed.stdout+completed.stderr
    result=json.loads((out/'result.json').read_bytes())
    assert result['parameters_updated'] and result['checkpoint_reloaded']
    assert result['source_sha256']==pin and result['real_oos']=='BLOCKED'
    assert sha256((out/'checkpoint.json').read_bytes()).hexdigest()==result['model_sha256']
    assert len(result['forecasts'])==result['test_count']==18
    assert {p['prediction']['instrument']['symbol'] for p in result['forecasts']}=={'BTCUSDT','ETHUSDT','SOLUSDT'}
    assert {p['timeframe_ns'] for p in result['forecasts']}=={60,120}
    assert all(p['prediction']['model_sha256']==result['model_sha256'] for p in result['forecasts'])
    from strattester.research.financial_evaluation import Trade,evaluate_ledger
    import math
    trades=[]
    for row in result['forecasts']:
        p=row['prediction'];instrument=p['instrument'];identity='|'.join((instrument['exchange'],instrument['market_type'],instrument['symbol'],str(row['timeframe_ns'])))
        trades.append(Trade(identity,p['origin_ns'],p['origin_ns']+p['horizon_ns'],math.expm1(row['forward_log_return']),int(p['mu']>result['threshold'])-int(p['mu'] < -result['threshold'])))
    assert evaluate_ledger(trades,fee_bps=2.,slippage_bps=1.)==result['ledger']
    again=subprocess.run(command,capture_output=True,text=True,timeout=60)
    assert again.returncode==2 and sha256((out/'checkpoint.json').read_bytes()).hexdigest()==result['model_sha256']

def test_experiment_denies_unpinned_unenabled_real_scope_and_cancellation(tmp_path):
    path,pin,payload=source(tmp_path)
    from strattester.research.financial_experiment_session import run_experiment_file
    with pytest.raises(ValueError,match='enable'):run_experiment_file(path,pin,tmp_path/'disabled')
    with pytest.raises(ValueError,match='SHA256'):run_experiment_file(path,'0'*64,tmp_path/'bad',enable_research=True)
    payload['scope']='PRODUCER_ATTESTED_RESEARCH';data=canonical_bytes(payload);path.write_bytes(data)
    with pytest.raises(ValueError,match='synthetic'):run_experiment_file(path,sha256(data).hexdigest(),tmp_path/'real',enable_research=True)
    from strattester.research.financial_training import TrainingCancelled
    with pytest.raises(TrainingCancelled):run_experiment_file(path,pin,tmp_path/'cancel',enable_research=True,cancel=lambda:True)
    assert not any((tmp_path/name).exists() for name in ('disabled','bad','real','cancel'))

def test_experiment_exact_schema_and_preparation_budget_fail_without_publication(tmp_path):
    path,pin,payload=source(tmp_path)
    from strattester.research.financial_experiment_session import run_experiment_file
    payload['unexpected']='denied';data=canonical_bytes(payload);path.write_bytes(data)
    with pytest.raises(ValueError,match='schema'):run_experiment_file(path,sha256(data).hexdigest(),tmp_path/'schema',enable_research=True)
    del payload['unexpected'];payload['config']['max_work_bytes']=2_000_000
    data=canonical_bytes(payload);path.write_bytes(data)
    with pytest.raises(ValueError,match='budget'):run_experiment_file(path,sha256(data).hexdigest(),tmp_path/'budget',enable_research=True)
    assert not (tmp_path/'schema').exists() and not (tmp_path/'budget').exists()
