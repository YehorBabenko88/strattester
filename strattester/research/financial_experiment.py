"""Reproducible engineering experiment, never proof of real-market OOS success.

Real-data authorization/provenance and GPU/reference gates are assessed outside
this harness. Direct in-memory Examples are always labelled synthetic research.
"""
from dataclasses import dataclass, asdict
import math
from hashlib import sha256
from statistics import mean
from .financial_contract import Snapshot, Instrument, integer, finite
from .financial_snapshot import canonical_bytes
from .financial_pipeline import feature_tracks
from .financial_structural_model import StructuralConfig, build_structural_model
from .financial_training import fit_structural
from .financial_checkpoint import save_checkpoint
from .financial_evaluation import Trade,evaluate_ledger,gaussian_scores,evaluate_controls


@dataclass(frozen=True)
class Example:
    snapshot: Snapshot
    target: Instrument
    timeframe_ns: int
    label_end_ns: int
    forward_log_return: float


def run_experiment(examples,checkpoint_path,*,train_end,validation_end,test_end,holdout_symbols=frozenset(),
                   config=StructuralConfig(),steps=20,seed=0,fee_bps=1.,slippage_bps=1.,embargo_ns=0,cancel=lambda:False):
    import torch
    from research.alphafold_training.evaluation import Sample,purged_split,fingerprint,bootstrap_mean_ci
    from research.alphafold_training.gates import assert_no_cross_partition_label_overlap
    integer(seed,'seed');integer(embargo_ns,'embargo')
    for value in (train_end,validation_end,test_end):integer(value,'split boundary',1)
    for cost in (fee_bps,slippage_bps):
        if finite(cost,'cost')<0:raise ValueError('invalid costs')
    if not examples or len(examples)>1024:raise ValueError('experiment sample budget')
    tensors={};masks={};records={};samples=[]
    config.validate()
    for e in examples:
        e.snapshot.validate();e.target.validate();integer(e.timeframe_ns,'timeframe',1);integer(e.label_end_ns,'label_end',1)
        if e.label_end_ns<=e.snapshot.origin_ns or (e.label_end_ns-e.snapshot.origin_ns)%e.timeframe_ns:
            raise ValueError('invalid label horizon')
        finite(e.forward_log_return,'label')
        x,m,identities=feature_tracks(e.snapshot,timeframe_ns=e.timeframe_ns,config=config)
        if e.target not in identities:raise ValueError('missing target')
        target=identities.index(e.target);order=[target,*[i for i in range(len(identities)) if i!=target]]
        key=(e.target.exchange,e.target.market_type,e.target.symbol,e.timeframe_ns,e.snapshot.origin_ns)
        if key in records:raise ValueError('duplicate experiment sample')
        instrument='|'.join(map(str,key[:4]))
        s=Sample(instrument,e.snapshot.origin_ns,e.label_end_ns,e.snapshot.origin_ns,tuple(x[0,target,-1].tolist()),e.forward_log_return)
        samples.append(s);tensors[key]=x[:,order];masks[key]=m[:,order];records[key]=asdict(e)
    ordered=sorted(samples,key=lambda s:(s.decision_time,s.instrument))
    train,val,test=purged_split(ordered,train_end,validation_end,test_end,embargo_ns)
    def key_for(s):
        a,b,c,tf=s.instrument.split('|')
        return a,b,c,int(tf),s.decision_time
    train=[s for s in train if key_for(s)[2] not in holdout_symbols]
    if not train or not val or not test:raise ValueError('nonempty chronological partitions required')
    assert_no_cross_partition_label_overlap(train,val,test)
    # Check every evaluation interval before training or publishing artifacts.
    for partition in (val,test):
        evaluate_ledger([Trade(s.instrument,s.decision_time,s.label_end_time,math.expm1(s.forward_return),0) for s in partition])
    if len({tuple(x.shape[1:]) for x in tensors.values()})!=1:raise ValueError('fixed aligned window shape required; no implicit padding')
    torch.manual_seed(seed)
    model=build_structural_model(config)
    before={n:p.detach().clone() for n,p in model.named_parameters()}
    x=torch.cat([tensors[key_for(s)] for s in train]);mask=torch.cat([masks[key_for(s)] for s in train])
    y=torch.tensor([s.forward_return for s in train],dtype=torch.float32)
    losses=fit_structural(model,x,y,mask,seed=seed,steps=steps,cancel=cancel)
    changed=any(not torch.equal(before[n],p) for n,p in model.named_parameters())
    if not changed:raise ValueError('optimizer did not update parameters')
    train_digest=fingerprint([records[key_for(s)] for s in train])
    model_digest=save_checkpoint(model,checkpoint_path,dataset_sha256=train_digest,seed=seed)
    model.eval()
    def predictions(partition):
        with torch.no_grad():return [model(tensors[key_for(s)],masks[key_for(s)])[0].tolist() for s in partition]
    validation=predictions(val)
    def ledger(partition,preds,threshold):
        return evaluate_ledger([Trade(s.instrument,s.decision_time,s.label_end_time,math.expm1(s.forward_return),
                                     int(p[0]>threshold)-int(p[0]<-threshold)) for s,p in zip(partition,preds)],
                               fee_bps=fee_bps,slippage_bps=slippage_bps)
    threshold=max((0.,.0005,.001,.002),key=lambda t:ledger(val,validation,t)['mean'])
    # The test predictions are requested only after freezing validation choice.
    predictions_test=predictions(test);net=ledger(test,predictions_test,threshold)
    controls=evaluate_controls([s.features for s in train],[s.forward_return for s in train],
                               [s.features for s in test],[s.forward_return for s in test],seed=seed)
    return {'status':'SYNTHETIC_ENGINEERING_ONLY','real_oos':'BLOCKED','seed':seed,'config':asdict(config),
            'dataset_sha256':fingerprint([records[k] for k in sorted(records)]),'training_dataset_sha256':train_digest,
            'model_sha256':model_digest,'train_count':len(train),'validation_count':len(val),'test_count':len(test),
            'holdout_count':sum(key_for(s)[2] in holdout_symbols for s in test),'parameters_updated':changed,
            'losses':losses,'threshold':threshold,'controls':controls,'ledger':net,
            'exploratory_ci':bootstrap_mean_ci(net['returns'],seed=seed,block_size=min(3,len(test))),
            'test_metrics':gaussian_scores([p[0] for p in predictions_test],[p[1] for p in predictions_test],[s.forward_return for s in test])}
