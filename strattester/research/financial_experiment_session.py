"""Pinned synthetic-label experiment files; never producer or trading authority."""
from dataclasses import asdict,fields
from pathlib import Path
import math
import os
import tempfile
from .financial_contract import Instrument,Bar,Snapshot,integer
from .financial_snapshot import bounded_json,verified_bytes,reject_linked_path,canonical_bytes
from .financial_structural_model import StructuralConfig
from .financial_experiment import Example,run_experiment
from .financial_session import check_cancel

SOURCE_KEYS={'version','scope','examples','config','train_end','validation_end','test_end','holdout_symbols','steps','seed','fee_bps','slippage_bps','embargo_ns'}

def exact(value,keys):
    if type(value) is not dict or set(value)!=set(keys):raise ValueError('exact experiment schema required')
    return value

def decode_examples(payload,cancel):
    rows=payload['examples']
    if type(rows) is not list or not 1<=len(rows)<=1024:raise ValueError('experiment example budget')
    examples=[];total_bars=0
    for row in rows:
        check_cancel(cancel);exact(row,(f.name for f in fields(Example)))
        snapshot=exact(row['snapshot'],(f.name for f in fields(Snapshot)))
        if type(snapshot['bars']) is not list or type(snapshot['producers']) is not list:raise ValueError('snapshot sequence schema')
        total_bars+=len(snapshot['bars'])
        if total_bars>100_000:raise ValueError('aggregate bar budget')
        bars=[]
        for raw in snapshot['bars']:
            check_cancel(cancel);exact(raw,(f.name for f in fields(Bar)))
            instrument=Instrument(**exact(raw['instrument'],(f.name for f in fields(Instrument))))
            bars.append(Bar(**{**raw,'instrument':instrument}))
        typed=Snapshot(tuple(bars),snapshot['origin_ns'],snapshot['coherence_id'],tuple(snapshot['producers'])).validate()
        target=Instrument(**exact(row['target'],(f.name for f in fields(Instrument))))
        target.validate()
        examples.append(Example(typed,target,row['timeframe_ns'],row['label_end_ns'],row['forward_log_return']))
    return examples

def run_experiment_file(source_path,source_sha256,output_dir,*,enable_research=False,cancel=lambda:False):
    check_cancel(cancel)
    if enable_research is not True:raise ValueError('explicit --enable-research required')
    data=verified_bytes(source_path,source_sha256,4*1024*1024)
    payload=exact(bounded_json(data),SOURCE_KEYS)
    if type(payload['version']) is not int or payload['version']!=1:raise ValueError('experiment version')
    if payload['scope']!='SYNTHETIC_ENGINEERING_ONLY':raise ValueError('direct labels restricted to synthetic engineering; real OOS blocked')
    config=StructuralConfig(**exact(payload['config'],(f.name for f in fields(StructuralConfig)))).validate()
    if config.max_work_bytes+len(data)*16>512*1024*1024:raise ValueError('aggregate serialized and model work budget')
    integer(payload['steps'],'steps',1)
    if payload['steps']>1000:raise ValueError('training step budget')
    examples=decode_examples(payload,cancel)
    options={k:payload[k] for k in ('train_end','validation_end','test_end','holdout_symbols','steps','seed','fee_bps','slippage_bps','embargo_ns')}
    target=Path(output_dir);root=reject_linked_path(target.parent)
    if target.exists() or target.is_symlink():raise ValueError('output exists; refusing overwrite')
    check_cancel(cancel)
    with tempfile.TemporaryDirectory(prefix='.experiment-',dir=root) as stage:
        stage=Path(stage);checkpoint=stage/'checkpoint.json'
        result=run_experiment(examples,checkpoint,config=config,cancel=cancel,**options)
        check_cancel(cancel)
        from .financial_checkpoint import load_checkpoint
        model,metadata=load_checkpoint(checkpoint,result['model_sha256'])
        if metadata['dataset_sha256']!=result['training_dataset_sha256']:raise ValueError('checkpoint training provenance mismatch')
        from .financial_pipeline import predict_snapshot
        from .financial_evaluation import Trade,evaluate_ledger,gaussian_scores
        test=sorted((e for e in examples if payload['validation_end']<=e.snapshot.origin_ns<payload['test_end'] and e.label_end_ns<=payload['test_end']),key=lambda e:(e.snapshot.origin_ns,'|'.join((e.target.exchange,e.target.market_type,e.target.symbol,str(e.timeframe_ns)))))
        forecasts=[];trades=[];mus=[];scales=[];labels=[]
        for example in test:
            check_cancel(cancel)
            prediction=predict_snapshot(example.snapshot,model,instrument=example.target,timeframe_ns=example.timeframe_ns,horizon_ns=config.horizon_ns,model_sha256=result['model_sha256'],available_ns=example.snapshot.origin_ns)
            identity='|'.join((example.target.exchange,example.target.market_type,example.target.symbol,str(example.timeframe_ns)))
            position=int(prediction.mu>result['threshold'])-int(prediction.mu < -result['threshold'])
            trades.append(Trade(identity,prediction.available_ns,example.label_end_ns,math.expm1(example.forward_log_return),position))
            forecasts.append({'prediction':asdict(prediction),'timeframe_ns':example.timeframe_ns,'label_end_ns':example.label_end_ns,'forward_log_return':example.forward_log_return,'position':position})
            mus.append(prediction.mu);scales.append(prediction.scale);labels.append(example.forward_log_return)
        ledger=evaluate_ledger(trades,fee_bps=payload['fee_bps'],slippage_bps=payload['slippage_bps'])
        metrics=gaussian_scores(mus,scales,labels)
        if ledger!=result['ledger'] or metrics!=result['test_metrics']:raise ValueError('verified checkpoint replay differs from experiment evaluation')
        result.update(source_sha256=source_sha256,source_bytes=len(data),checkpoint_reloaded=True,forecasts=forecasts,ledger=ledger,test_metrics=metrics,physical_g1='NOT_AUTHORIZED',trading='NO-GO',native_resource_caps='NOT_ENFORCED',prediction_availability='SYNTHETIC_ORIGIN_ONLY_NOT_DEPLOYMENT_LATENCY')
        encoded=canonical_bytes(result)
        if len(encoded)>4*1024*1024:raise ValueError('experiment output budget')
        check_cancel(cancel)
        with (stage/'result.json').open('xb') as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        check_cancel(cancel)
        if target.exists() or target.is_symlink():raise ValueError('output exists; refusing overwrite')
        os.rename(stage,target)
    return {'status':'SYNTHETIC_ENGINEERING_ONLY','real_oos':'BLOCKED','source_sha256':source_sha256,'model_sha256':result['model_sha256'],'test_count':len(forecasts),'output':str(target),'trading':'NO-GO','physical_g1':'NOT_AUTHORIZED','native_resource_caps':'NOT_ENFORCED'}
