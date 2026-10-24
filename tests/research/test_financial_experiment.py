from dataclasses import replace
import pytest
from strattester.research.financial_contract import Instrument,Bar,Snapshot
from strattester.research.financial_experiment import Example, run_experiment
from strattester.research.financial_structural_model import StructuralConfig


def examples():
    out=[]
    for origin in (360,720,1080,1440,1800,2160,2520,2880,3240):
        for tf in (60,120):
            rows=[]
            for symbol in ('BTCUSDT','ETHUSDT'):
                for j in range(3):
                    t=origin-(3-j)*tf
                    rows.append(Bar(Instrument('bybit','linear',symbol),tf,t,t+tf,t+tf-1,t+tf,t+tf,origin,
                                    100.+j+(origin/10000 if symbol=='BTCUSDT' else -origin/10000),
                                    'VERIFIED',True,True,1,'fixture','a'*40))
            snapshot=Snapshot(tuple(rows),origin,'fixture-epoch',('fixture',))
            for symbol in ('BTCUSDT','ETHUSDT'):
                out.append(Example(snapshot,Instrument('bybit','linear',symbol),tf,origin+tf,.001 if symbol=='BTCUSDT' else -.001))
    return out


def test_multi_instrument_timeframe_purged_experiment_records_real_updates(tmp_path):
    cfg=StructuralConfig(recycles=0)
    result=run_experiment(examples(),tmp_path/'model.json',train_end=1200,validation_end=2400,test_end=3400,
                          holdout_symbols={'ETHUSDT'},config=cfg,steps=1,seed=12)
    assert result['status']=='SYNTHETIC_ENGINEERING_ONLY'
    assert result['train_count']==6 and result['test_count']==12
    assert result['holdout_count']==6 and result['parameters_updated']
    assert result['real_oos']=='BLOCKED'
    assert len(result['model_sha256'])==64 and len(result['dataset_sha256'])==64
    assert result['test_metrics']['nll']>0
    assert set(result['controls'])=={'zero','mean','persistence','linear','random_signal','label_shuffle','delayed_feature'}


def test_future_dependency_blocks_before_checkpoint(tmp_path):
    rows=examples();first=rows[0];bar=replace(first.snapshot.bars[0],available_ns=99999)
    rows[0]=replace(first,snapshot=replace(first.snapshot,bars=(bar,*first.snapshot.bars[1:])))
    path=tmp_path/'model.json'
    with pytest.raises(ValueError):run_experiment(rows,path,train_end=1200,validation_end=2400,test_end=3400,steps=1)
    assert not path.exists()
