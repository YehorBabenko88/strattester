from dataclasses import replace
import json
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
                out.append(Example(snapshot,Instrument('bybit','linear',symbol),tf,origin+120,.001 if symbol=='BTCUSDT' else -.001))
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


def test_mixed_unconditioned_horizons_are_rejected(tmp_path):
    rows=examples()
    rows[0]=replace(rows[0],label_end_ns=rows[0].snapshot.origin_ns+60)
    with pytest.raises(ValueError,match='horizon'):
        run_experiment(rows,tmp_path/'model.json',train_end=1200,validation_end=2400,test_end=3400,steps=1)


def test_instrument_holdout_is_absent_from_training_context(tmp_path):
    original=examples();changed=[]
    for example in original:
        if example.snapshot.origin_ns<1200:
            altered=tuple(replace(b,close=b.close*2+(b.candle_open_ns%100)) if b.instrument.symbol=='ETHUSDT' else b for b in example.snapshot.bars)
            example=replace(example,snapshot=replace(example.snapshot,bars=altered))
        changed.append(example)
    kwargs=dict(train_end=1200,validation_end=2400,test_end=3400,steps=1,seed=3,holdout_symbols={'ETHUSDT'})
    a=tmp_path/'a.json';b=tmp_path/'b.json'
    run_experiment(original,a,**kwargs);run_experiment(changed,b,**kwargs)
    assert json.loads(a.read_text())['tensors']==json.loads(b.read_text())['tensors']


def test_evaluation_failure_cannot_publish_checkpoint(tmp_path,monkeypatch):
    import strattester.research.financial_experiment as experiment
    def fail(*args,**kwargs):raise ValueError('evaluation failed')
    monkeypatch.setattr(experiment,'gaussian_scores',fail)
    path=tmp_path/'model.json'
    with pytest.raises(ValueError,match='evaluation failed'):
        run_experiment(examples(),path,train_end=1200,validation_end=2400,test_end=3400,steps=1)
    assert not path.exists()
