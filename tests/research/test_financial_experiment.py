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


def extended_examples():
    rows=examples();shifted=[]
    names=('candle_open_ns','candle_close_ns','event_ns','ingest_ns','available_ns','watermark_ns')
    for e in rows:
        bars=tuple(replace(b,**{name:getattr(b,name)+3240 for name in names}) for b in e.snapshot.bars)
        snapshot=replace(e.snapshot,bars=bars,origin_ns=e.snapshot.origin_ns+3240)
        shifted.append(replace(e,snapshot=snapshot,label_end_ns=e.label_end_ns+3240))
    return [*rows,*shifted]


def test_neural_walk_forward_retrains_fresh_models_and_keeps_fold_evidence(tmp_path):
    from strattester.research.financial_experiment import run_walk_forward
    r=run_walk_forward(extended_examples(),tmp_path/'folds',[(1200,2400,3400),(4500,5400,6600)],
                       config=StructuralConfig(recycles=0),steps=1,seed=8,allow_retraining_on_prior_oos=True)
    assert r['fold_count']==2 and r['fold_independence']=='SEQUENTIAL_RETRAINING'
    # Second test interval includes its 5400 boundary: 5400,5760,6120,6480,
    # with two instruments and two timeframes at each origin.
    assert [fold['test_count'] for fold in r['folds']]==[12,16]
    assert all(fold['parameters_updated'] for fold in r['folds'])
    assert r['folds'][0]['model_sha256']!=r['folds'][1]['model_sha256']
    assert r['folds'][1]['research_config']['train_end']==4500
    assert r['real_oos']=='BLOCKED'


def test_walk_forward_rejects_overlapping_or_reused_holdouts_before_artifacts(tmp_path):
    from strattester.research.financial_experiment import run_walk_forward
    root=tmp_path/'folds'
    with pytest.raises(ValueError,match='prior OOS'):
        run_walk_forward(extended_examples(),root,[(1200,2400,3400),(4500,5400,6600)],steps=1)
    assert not root.exists()
    with pytest.raises(ValueError,match='overlap'):
        run_walk_forward(extended_examples(),root,[(1200,2400,3400),(1800,2880,4500)],steps=1,allow_retraining_on_prior_oos=True)
    assert not root.exists()


def test_preparation_cancel_precedes_feature_allocation(tmp_path, monkeypatch):
    import strattester.research.financial_experiment as experiment
    from strattester.research.financial_training import TrainingCancelled
    def allocate(*args, **kwargs):
        pytest.fail('feature allocation occurred after cancellation')
    monkeypatch.setattr(experiment, 'feature_tracks', allocate)
    with pytest.raises(TrainingCancelled):
        run_experiment(examples(), tmp_path/'cancel.json', train_end=1200,
                       validation_end=2400, test_end=3400, cancel=lambda: True)


def test_aggregate_admission_precedes_feature_allocation(tmp_path, monkeypatch):
    import strattester.research.financial_experiment as experiment
    def allocate(*args, **kwargs):
        pytest.fail('feature allocation preceded aggregate admission')
    monkeypatch.setattr(experiment, 'feature_tracks', allocate)
    cfg=StructuralConfig(recycles=0, max_work_bytes=2_000_000)
    with pytest.raises(ValueError, match='aggregate preparation budget'):
        run_experiment(examples(), tmp_path/'budget.json', train_end=1200,
                       validation_end=2400, test_end=3400, config=cfg)


def test_streaming_fingerprint_preserves_existing_dataset_identity():
    from dataclasses import asdict
    from research.alphafold_training.evaluation import fingerprint
    from strattester.research.financial_experiment import _example_fingerprint
    rows=examples()
    assert _example_fingerprint(iter(rows),lambda:False)==fingerprint([asdict(e) for e in rows])


def test_cancel_between_feature_examples_leaves_no_artifact(tmp_path, monkeypatch):
    import strattester.research.financial_experiment as experiment
    from strattester.research.financial_training import TrainingCancelled
    original=experiment.feature_tracks;allocated=[]
    def tracked(*args, **kwargs):
        allocated.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(experiment,'feature_tracks',tracked)
    path=tmp_path/'cancel-mid.json'
    with pytest.raises(TrainingCancelled):
        run_experiment(examples(),path,train_end=1200,validation_end=2400,test_end=3400,
                       cancel=lambda:bool(allocated))
    assert len(allocated)==1 and not path.exists()


def test_walk_forward_caps_generator_consumption_before_artifacts(tmp_path):
    from strattester.research.financial_experiment import run_walk_forward
    consumed=[]
    first=examples()[0]
    def rows():
        for i in range(1100):
            consumed.append(i)
            yield first
    with pytest.raises(ValueError,match='walk-forward resource budget'):
        run_walk_forward(rows(),tmp_path/'folds',[(1200,2400,3400)])
    assert len(consumed)==1025
    assert not (tmp_path/'folds').exists()


def test_malformed_holdout_policy_fails_before_checkpoint_publication(tmp_path):
    path=tmp_path/'invalid-holdout.json'
    with pytest.raises(ValueError,match='holdout symbols'):
        run_experiment(examples(),path,train_end=1200,validation_end=2400,test_end=3400,
                       steps=1,holdout_symbols={'ETHUSDT',None})
    assert not path.exists()
