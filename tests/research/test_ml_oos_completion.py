"""Independent synthetic arithmetic and leakage/recovery regressions."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import runpy

import pytest


def test_validation_scale_mle_and_finite_contract():
    from strattester.research.financial_calibration import fit_scale_calibration, calibrated_scores
    state = fit_scale_calibration([0., 0.], [1., 2.], [2., -4.])
    assert state['scale_multiplier'] == 2.
    assert state['fit_count'] == 2 and state['fit_partition'] == 'VALIDATION_ONLY'
    score = calibrated_scores([0.], [1.], [2.], state)
    assert score['nll'] == pytest.approx(2.112085713764618)
    assert score['coverage_95'] == 1.
    for args in (([], [], []), ([0.], [0.], [1.]), ([0.], [1.], [float('nan')])):
        with pytest.raises(ValueError): fit_scale_calibration(*args)


def test_ledger_itemizes_signed_cashflows_and_roundtrip_costs():
    from strattester.research.financial_evaluation import Trade, evaluate_ledger
    from strattester.research.financial_funding import FundingEvent, FundingWindow
    window = FundingWindow('v/perp/A', 0, 20, 20, 'a'*64,
        (FundingEvent('v/perp/A', 'settle', 10, 10, '20', 'bps'),))
    r = evaluate_ledger([Trade('v/perp/A', 0, 10, .1, -1)], fee_bps=10,
        slippage_bps=5, funding_windows=(window,))
    row = r['rows'][0]
    assert row['gross_return'] == -.1
    assert row['fee_cost'] == .002 and row['slippage_cost'] == .001
    assert row['funding_cashflow'] == .002
    assert row['net_return'] == pytest.approx(-.101)
    assert r['returns'] == [row['net_return']]


def _examples():
    return runpy.run_path(str(Path(__file__).with_name('test_financial_experiment.py')))['examples']()


def test_test_labels_never_change_weights_calibration_or_threshold(tmp_path):
    from strattester.research.financial_experiment import run_experiment
    from strattester.research.financial_structural_model import StructuralConfig
    rows = _examples()
    options = dict(train_end=1200, validation_end=2400, test_end=3400,
        config=StructuralConfig(recycles=0), steps=1, seed=18, holdout_symbols=['ETHUSDT'])
    a = run_experiment(rows, tmp_path/'a.json', **options)
    b = run_experiment([replace(e, forward_log_return=e.forward_log_return+.5)
        if e.snapshot.origin_ns >= 2400 else e for e in rows], tmp_path/'b.json', **options)
    assert a['model_sha256'] == b['model_sha256']
    assert a['calibration'] == b['calibration']
    assert a['threshold'] == b['threshold']
    assert {k:v['threshold'] for k,v in a['control_scorecards'].items()} == {k:v['threshold'] for k,v in b['control_scorecards'].items()}
    assert a['calibrated_test_metrics'] != b['calibrated_test_metrics']
    assert a['training_instruments'] == ['bybit|linear|BTCUSDT|120', 'bybit|linear|BTCUSDT|60']


def test_checkpoint_recovery_requires_external_pin_and_never_adopts_orphans(tmp_path):
    from strattester.research.financial_checkpoint import save_checkpoint, inspect_checkpoint_recovery
    from strattester.research.financial_structural_model import StructuralConfig, build_structural_model
    path=tmp_path/'checkpoint.json'
    pin=save_checkpoint(build_structural_model(StructuralConfig(recycles=0)), path,
        dataset_sha256='a'*64, seed=4)
    orphan=tmp_path/'.checkpoint-orphan'; orphan.write_bytes(b'partial')
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    result=inspect_checkpoint_recovery(path, pin, dataset_sha256='a'*64, seed=4)
    assert result['status']=='VERIFIED_MODEL_ONLY_RESTART_REQUIRED'
    assert result['optimizer_resume'] is False
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before
    with pytest.raises(ValueError): inspect_checkpoint_recovery(path, '0'*64, dataset_sha256='a'*64, seed=4)
    with pytest.raises(ValueError): inspect_checkpoint_recovery(path, pin, dataset_sha256='b'*64, seed=4)
    with pytest.raises(ValueError): inspect_checkpoint_recovery(orphan, sha256(b'partial').hexdigest(), dataset_sha256='a'*64, seed=4)


def test_late_fold_failure_publishes_no_checkpoint_and_restart_is_deterministic(tmp_path,monkeypatch):
    import strattester.research.financial_experiment as experiment
    from strattester.research.financial_structural_model import StructuralConfig
    rows=runpy.run_path(str(Path(__file__).with_name('test_financial_experiment.py')))['extended_examples']()
    options=dict(config=StructuralConfig(recycles=0),steps=1,seed=8,allow_retraining_on_prior_oos=True)
    folds=[(1200,2400,3400),(4500,5400,6600)]
    original=experiment.run_experiment;calls=[]
    def fail_second(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:raise RuntimeError('synthetic late-fold failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(experiment,'run_experiment',fail_second)
    with pytest.raises(RuntimeError,match='late-fold'):
        experiment.run_walk_forward(rows,tmp_path/'retry',folds,**options)
    assert not list((tmp_path/'retry').glob('fold-*.json'))
    monkeypatch.setattr(experiment,'run_experiment',original)
    recovered=experiment.run_walk_forward(rows,tmp_path/'retry',folds,**options)
    clean=experiment.run_walk_forward(rows,tmp_path/'clean',folds,**options)
    assert recovered==clean


def test_baseline_scorecards_have_validation_frozen_thresholds_and_costs(tmp_path):
    from strattester.research.financial_experiment import run_experiment
    from strattester.research.financial_structural_model import StructuralConfig
    result=run_experiment(_examples(),tmp_path/'m.json',train_end=1200,validation_end=2400,
        test_end=3400,config=StructuralConfig(recycles=0),steps=1,seed=7,fee_bps=10,slippage_bps=5)
    cards=result['control_scorecards']
    assert set(cards)=={'zero','mean','persistence','linear','random_signal','label_shuffle','delayed_feature'}
    assert cards['zero']['ledger']['returns']==[0.]*12
    assert cards['zero']['selection_partition']=='VALIDATION_ONLY'
    assert cards['persistence']['ledger']['turnover']==24
    assert all(r['fee_cost']==.002 and r['slippage_cost']==.001 for r in cards['persistence']['ledger']['rows'])


def test_heldout_validation_labels_cannot_select_calibration_or_threshold(tmp_path):
    from strattester.research.financial_experiment import run_experiment
    from strattester.research.financial_structural_model import StructuralConfig
    options=dict(train_end=1200,validation_end=2400,test_end=3400,
        config=StructuralConfig(recycles=0),steps=1,seed=18,holdout_symbols=['ETHUSDT'])
    rows=_examples()
    a=run_experiment(rows,tmp_path/'a.json',**options)
    changed=[replace(e,forward_log_return=.5) if e.target.symbol=='ETHUSDT'
             and 1200<=e.snapshot.origin_ns<2400 else e for e in rows]
    b=run_experiment(changed,tmp_path/'b.json',**options)
    assert a['calibration']==b['calibration']
    assert a['threshold']==b['threshold']
    assert a['calibration']['fit_count']==6
