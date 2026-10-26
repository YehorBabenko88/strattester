"""Signed multi-origin software evidence, with independent ledger arithmetic."""
from dataclasses import asdict
from hashlib import sha256
import runpy
from pathlib import Path
import json
import math
import subprocess
import sys
import pytest
from strattester.research.financial_contract import Bar, Instrument, Snapshot
from strattester.research.financial_snapshot import canonical_bytes, snapshot_bytes


def source(tmp_path):
    fixture = runpy.run_path(str(Path(__file__).with_name('signed_export_fixture.py')))['bundle'](tmp_path / 'keys')
    exports = []; labels = []
    for index, origin in enumerate(range(360, 4321, 360)):
        bars = []
        for tf in (60, 120):
            for k, symbol in enumerate(('BTCUSDT', 'ETHUSDT', 'SOLUSDT')):
                for j in range(3):
                    t = origin - (3-j)*tf
                    bars.append(Bar(Instrument('bybit', 'linear', symbol), tf, t, t+tf, t+tf-1, t+tf, t+tf, origin, 100.+j+k+origin/10000, 'VERIFIED', True, True, 1, 'fixture-grid', 'a'*40))
                labels.append(dict(export_index=index, target=asdict(Instrument('bybit','linear',symbol)), timeframe_ns=tf, label_end_ns=origin+120, forward_log_return=.001*(k-1)))
        snapshot = Snapshot(tuple(bars), origin, 'epoch-fixture', ('fixture-grid',))
        data = snapshot_bytes(snapshot); name = f'snapshot-{index}.json'; (tmp_path/name).write_bytes(data)
        m = {**fixture['manifest'], 'export_id':f'cut-{index}', 'snapshot_sha256':sha256(data).hexdigest(), 'snapshot_bytes':len(data), 'row_count':len(bars), 'knowledge_cutoff_ns':origin, 'issued_at_ns':origin+1,
             'partitions':[dict(exchange='bybit',market_type='linear',symbol=s,timeframe_ns=tf) for tf in (60,120) for s in ('BTCUSDT','ETHUSDT','SOLUSDT')]}
        m['sources'] = [{**m['sources'][0], 'snapshot_id':f'cut-{index}', 'event_watermark_ns':origin, 'availability_watermark_ns':origin}]
        pin = fixture['publish'](m); manifest_name=f'manifest-{index}.json'; (tmp_path/manifest_name).write_bytes((fixture['root']/'manifest.json').read_bytes())
        policy={**asdict(fixture['policy']), 'knowledge_cutoff_ns':origin, 'verification_ns':origin+10, 'partitions':m['partitions']}
        exports.append(dict(manifest_path=manifest_name, manifest_sha256=pin, snapshot_path=name, policy=policy))
    for name in ('trust.json','checkpoint.json'):(tmp_path/name).write_bytes((fixture['root']/name).read_bytes())
    from strattester.research.financial_checkpoint import load_checkpoint, save_checkpoint
    from strattester.research.financial_structural_model import StructuralConfig, build_structural_model
    # Bootstrap pin is external to the dataset, as is trust; its horizon matches both frames.
    (tmp_path/'checkpoint.json').unlink()
    config=StructuralConfig(recycles=0, max_batch=32)
    bootstrap=save_checkpoint(build_structural_model(config),tmp_path/'checkpoint.json',dataset_sha256='c'*64,seed=9)
    payload=dict(version=1,scope='SYNTHETIC_ENGINEERING_ONLY',label_contract='PINNED_SYNTHETIC_LOG_RETURNS_V1',exports=exports,labels=labels,config=asdict(config),folds=[[1200,2400,3400],[2400,3600,4800]],holdout_symbols=['SOLUSDT'],steps=1,seed=12,fee_bps=2.,slippage_bps=1.,embargo_ns=0,allow_retraining_on_prior_oos=True)
    path=tmp_path/'walkforward.json';data=canonical_bytes(payload);path.write_bytes(data)
    return path,sha256(data).hexdigest(),payload,fixture,bootstrap


def run(inputs, output, **kwargs):
    from strattester.research.financial_walkforward_session import run_walkforward_file
    path,pin,payload,fixture,bootstrap=inputs
    return run_walkforward_file(path,pin,output,trust_store_path=path.parent/'trust.json',trust_store_sha256=fixture['trust_sha'],checkpoint_path=path.parent/'checkpoint.json',checkpoint_sha256=bootstrap,verifier=fixture['verifier'],enable_research=True,**kwargs)


def test_signed_walkforward_replays_fresh_folds_and_independent_cost_ledger(tmp_path):
    inputs=source(tmp_path); out=tmp_path/'output'
    summary=run(inputs,out)
    report=json.loads((out/'report.json').read_bytes())
    assert summary['fold_count']==2 and summary['status']=='SYNTHETIC_ENGINEERING_ONLY'
    assert report['real_oos']=='BLOCKED' and report['funding']['status']=='BLOCKED'
    assert len(report['signed_exports'])==12 and len(report['bootstrap_predictions'])==72
    assert report['fold_independence']=='SEQUENTIAL_RETRAINING'
    assert [f['train_count'] for f in report['folds']]==[12,24]
    assert [f['holdout_count'] for f in report['folds']]==[6,6]
    assert report['folds'][0]['training_dataset_sha256']!=report['folds'][1]['training_dataset_sha256']
    for i, fold in enumerate(report['folds']):
        assert fold['parameters_updated'] and fold['checkpoint_reloaded']
        assert sha256((out/f'fold-{i:03d}.json').read_bytes()).hexdigest()==fold['model_sha256']
        assert len(fold['forecasts'])==fold['test_count']==18
        assert {f['timeframe_ns'] for f in fold['forecasts']}=={60,120}
        assert {f['prediction']['instrument']['symbol'] for f in fold['forecasts']}=={'BTCUSDT','ETHUSDT','SOLUSDT'}
        expected=[]
        for row in fold['forecasts']:
            p=row['prediction'];position=row['position']
            expected.append(position*math.expm1(row['forward_log_return'])-2*abs(position)*.0003)
            assert p['origin_ns']+120==row['label_end_ns']
            assert p['model_sha256']==fold['model_sha256']
        assert fold['ledger']['returns']==pytest.approx(expected)
    with pytest.raises(ValueError,match='exists'):run(inputs,out)


@pytest.mark.parametrize('mutation,match',[
    ('scope','synthetic'),('extra','schema'),('fold','overlapping'),('label','horizon'),('source','source'),('pin','SHA256'),('budget','budget')])
def test_invalid_signed_walkforward_never_publishes(tmp_path,mutation,match):
    inputs=list(source(tmp_path));path,pin,payload,fixture,bootstrap=inputs
    if mutation=='scope':payload['scope']='PRODUCER_ATTESTED_RESEARCH'
    if mutation=='extra':payload['unexpected']=True
    if mutation=='fold':payload['folds'][1]=payload['folds'][0]
    if mutation=='label':payload['labels'][0]['label_end_ns']+=1
    if mutation=='source':payload['exports'][0]['policy']['sources'][0]['source_id']='missing'
    if mutation=='pin':payload['exports'][0]['manifest_sha256']='0'*64
    if mutation=='budget':payload['steps']=1001
    data=canonical_bytes(payload);path.write_bytes(data);inputs[1]=sha256(data).hexdigest()
    with pytest.raises(ValueError,match=match):run(inputs,tmp_path/'output')
    assert not (tmp_path/'output').exists()
    assert not list(tmp_path.glob('.walkforward-*'))


def test_cancel_during_training_cleans_stage_and_allows_retry(tmp_path):
    inputs=source(tmp_path);calls=0
    def cancel():
        nonlocal calls
        calls+=1
        return bool(list(tmp_path.glob('.walkforward-*/fold-000.json')))
    from strattester.research.financial_training import TrainingCancelled
    with pytest.raises(TrainingCancelled):run(inputs,tmp_path/'output',cancel=cancel)
    assert calls>10 and not (tmp_path/'output').exists()
    assert not list(tmp_path.glob('.walkforward-*'))
    assert run(inputs,tmp_path/'retry')['fold_count']==2


def test_cli_requires_independent_trust_checkpoint_pins_and_runs_offline(tmp_path):
    inputs=source(tmp_path);path,pin,payload,fixture,bootstrap=inputs;v=fixture['verifier']
    offline="import socket,sys\ndef deny(*a,**k):raise AssertionError('offline network attempted')\nsocket.socket.connect=deny;socket.create_connection=deny\nfrom strattester.research_cli import main\nsys.exit(main(sys.argv[1:]))"
    command=[sys.executable,'-c',offline,'walk-forward','--source',str(path),'--source-sha256',pin,'--output',str(tmp_path/'cli'),'--trust-store',str(tmp_path/'trust.json'),'--trust-store-sha256',fixture['trust_sha'],'--checkpoint',str(tmp_path/'checkpoint.json'),'--checkpoint-sha256',bootstrap,'--openssl-exe',str(v.executable),'--openssl-sha256',v.executable_sha256,'--scratch-root',str(tmp_path),'--enable-research']
    completed=subprocess.run(command,capture_output=True,text=True,timeout=120)
    assert completed.returncode==0,completed.stdout+completed.stderr
    assert json.loads(completed.stdout)['fold_count']==2


def test_prepare_command_creates_reproducible_signed_dataset_for_custom_contract(tmp_path):
    from strattester.research.financial_walkforward_fixture import prepare_walkforward_fixture
    fixture=source(tmp_path);v=fixture[3]['verifier']
    instruments=[Instrument('venue-x','spot',s) for s in ('AAA','BBB','CCC')]
    args=dict(openssl_exe=v.executable,openssl_sha256=v.executable_sha256,scratch_root=tmp_path,seed=31,
              instruments=instruments,timeframes_ns=(10,20),horizon_ns=20)
    first=prepare_walkforward_fixture(tmp_path/'prepared',**args)
    second=prepare_walkforward_fixture(tmp_path/'prepared-again',**args)
    assert first['source_sha256']==second['source_sha256']
    from strattester.research.financial_walkforward_session import run_walkforward_file
    result=run_walkforward_file(first['source_path'],first['source_sha256'],tmp_path/'custom-output',
        trust_store_path=first['trust_store_path'],trust_store_sha256=first['trust_store_sha256'],
        checkpoint_path=first['checkpoint_path'],checkpoint_sha256=first['checkpoint_sha256'],verifier=v,enable_research=True)
    assert result['fold_count']==2
    report=json.loads((tmp_path/'custom-output'/'report.json').read_bytes())
    assert {p['instrument']['exchange'] for p in report['bootstrap_predictions']}=={'venue-x'}
    assert {p['horizon_ns'] for p in report['bootstrap_predictions']}=={20}


@pytest.mark.parametrize('kind',['trust','checkpoint','no-prior-oos','path','embargo'])
def test_external_pins_paths_and_explicit_sequential_policy_are_enforced(tmp_path,kind):
    inputs=list(source(tmp_path));path,pin,payload,fixture,bootstrap=inputs
    if kind=='trust':(tmp_path/'trust.json').write_bytes(b'{}')
    if kind=='checkpoint':inputs[4]='0'*64
    if kind=='no-prior-oos':payload['allow_retraining_on_prior_oos']=False
    if kind=='path':payload['exports'][0]['snapshot_path']='../keys/snapshot.json'
    if kind=='embargo':payload['embargo_ns']=1200
    data=canonical_bytes(payload);path.write_bytes(data);inputs[1]=sha256(data).hexdigest()
    with pytest.raises(ValueError):run(inputs,tmp_path/'output')
    assert not (tmp_path/'output').exists() and not list(tmp_path.glob('.walkforward-*'))


def test_changed_future_and_holdout_labels_cannot_change_first_fold_training(tmp_path):
    inputs=list(source(tmp_path));run(inputs,tmp_path/'first')
    first=json.loads((tmp_path/'first'/'report.json').read_bytes())
    path,pin,payload,fixture,bootstrap=inputs
    for row in payload['labels']:
        if row['export_index']>=3 or row['target']['symbol']=='SOLUSDT':row['forward_log_return']+=.03
    data=canonical_bytes(payload);path.write_bytes(data);inputs[1]=sha256(data).hexdigest()
    run(inputs,tmp_path/'changed');changed=json.loads((tmp_path/'changed'/'report.json').read_bytes())
    assert first['folds'][0]['model_sha256']==changed['folds'][0]['model_sha256']
    assert first['folds'][0]['training_dataset_sha256']==changed['folds'][0]['training_dataset_sha256']
    assert first['folds'][1]['training_dataset_sha256']!=changed['folds'][1]['training_dataset_sha256']
