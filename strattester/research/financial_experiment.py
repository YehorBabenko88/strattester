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
from .financial_training import fit_structural, TrainingCancelled
from .financial_checkpoint import save_checkpoint
from .financial_evaluation import Trade,evaluate_ledger,gaussian_scores,evaluate_controls


@dataclass(frozen=True)
class Example:
    snapshot: Snapshot
    target: Instrument
    timeframe_ns: int
    label_end_ns: int
    forward_log_return: float



def _admit_preparation(examples, config, cancel):
    """Conservative host preparation charge, separate from operator workspace.

    Charge duplicate snapshots per example even when inputs share objects.
    Reserve space for feature banks, advanced-index copies, concatenation,
    Python metadata, and canonical JSON expansion before producing any tensor.
    This is an admission bound, not a measurement of process RSS.
    """
    charge=0
    for example in examples:
        if cancel():raise TrainingCancelled('cancelled during experiment admission')
        charge+=16384
        for bar in example.snapshot.bars:
            if cancel():raise TrainingCancelled('cancelled during experiment admission')
            charge+=8192
            for value in (*vars(bar).values(),*vars(bar.instrument).values()):
                if isinstance(value,str):charge+=24*len(value)
                elif type(value) is int:charge+=16*(1+value.bit_length()//8)
            if charge>config.max_work_bytes:raise ValueError('aggregate preparation budget exceeded')
        # All banks and the train selection/concatenation coexist temporarily.
        charge+=4*config.max_tracks*config.max_tokens*(4*config.input_channels+1)
        charge+=24*(len(example.snapshot.coherence_id)+sum(map(len,example.snapshot.producers)))
        if charge>config.max_work_bytes:raise ValueError('aggregate preparation budget exceeded')


def _example_fingerprint(examples, cancel):
    """Hash the same canonical JSON array as fingerprint without a record bank."""
    import json
    encoder=json.JSONEncoder(sort_keys=True,separators=(',', ':'),allow_nan=False)
    digest=sha256();digest.update(b'[')
    for i,example in enumerate(examples):
        if cancel():raise TrainingCancelled('cancelled during dataset fingerprint')
        if i:digest.update(b',')
        for chunk in encoder.iterencode(asdict(example)):
            if cancel():raise TrainingCancelled('cancelled during dataset fingerprint')
            digest.update(chunk.encode('utf-8'))
    digest.update(b']')
    return digest.hexdigest()


def run_experiment(examples,checkpoint_path,*,train_end,validation_end,test_end,holdout_symbols=frozenset(),
                   config=StructuralConfig(),steps=20,seed=0,fee_bps=1.,slippage_bps=1.,embargo_ns=0,cancel=lambda:False):
    import torch
    from research.alphafold_training.evaluation import Sample,purged_split,bootstrap_mean_ci
    from research.alphafold_training.gates import assert_no_cross_partition_label_overlap
    integer(seed,'seed');integer(embargo_ns,'embargo')
    if (type(holdout_symbols) not in (set,frozenset,list,tuple) or len(holdout_symbols)>1024
        or any(not isinstance(symbol,str) or not symbol or symbol.strip()!=symbol for symbol in holdout_symbols)):
        raise ValueError('holdout symbols must be a bounded collection of nonempty identities')
    holdout_symbols=frozenset(holdout_symbols)
    for value in (train_end,validation_end,test_end):integer(value,'split boundary',1)
    for cost in (fee_bps,slippage_bps):
        if finite(cost,'cost')<0:raise ValueError('invalid costs')
    if not examples or len(examples)>1024:raise ValueError('experiment sample budget')
    tensors={};masks={};records={};samples=[];track_ids={}
    config.validate()
    _admit_preparation(examples,config,cancel)
    for e in examples:
        if cancel():raise TrainingCancelled('cancelled during experiment preparation')
        e.snapshot.validate();e.target.validate();integer(e.timeframe_ns,'timeframe',1);integer(e.label_end_ns,'label_end',1)
        if (e.label_end_ns-e.snapshot.origin_ns!=config.horizon_ns
            or config.horizon_ns%e.timeframe_ns):
            raise ValueError('invalid label horizon')
        finite(e.forward_log_return,'label')
        x,m,identities=feature_tracks(e.snapshot,timeframe_ns=e.timeframe_ns,config=config)
        if e.target not in identities:raise ValueError('missing target')
        target=identities.index(e.target);order=[target,*[i for i in range(len(identities)) if i!=target]]
        key=(e.target.exchange,e.target.market_type,e.target.symbol,e.timeframe_ns,e.snapshot.origin_ns)
        if key in records:raise ValueError('duplicate experiment sample')
        instrument='|'.join(map(str,key[:4]))
        s=Sample(instrument,e.snapshot.origin_ns,e.label_end_ns,e.snapshot.origin_ns,tuple(x[0,target,-1].tolist()),e.forward_log_return)
        samples.append(s);tensors[key]=x[:,order];masks[key]=m[:,order];records[key]=e
        track_ids[key]=[identities[i] for i in order]
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
    train_x=[];train_masks=[]
    for s in train:
        key=key_for(s)
        keep=[i for i,identity in enumerate(track_ids[key]) if identity.symbol not in holdout_symbols]
        if not keep or keep[0]!=0:raise ValueError('training target must not be held out')
        train_x.append(tensors[key][:,keep]);train_masks.append(masks[key][:,keep])
    if len({tuple(x.shape[1:]) for x in train_x})!=1:raise ValueError('aligned training context required')
    x=torch.cat(train_x);mask=torch.cat(train_masks)
    y=torch.tensor([s.forward_return for s in train],dtype=torch.float32)
    losses=fit_structural(model,x,y,mask,seed=seed,steps=steps,cancel=cancel)
    changed=any(not torch.equal(before[n],p) for n,p in model.named_parameters())
    if not changed:raise ValueError('optimizer did not update parameters')
    train_digest=_example_fingerprint((records[key_for(s)] for s in train),cancel)
    model.eval()
    def predictions(partition):
        result=[]
        with torch.no_grad():
            for s in partition:
                if cancel():raise TrainingCancelled('cancelled during experiment evaluation')
                result.append(model(tensors[key_for(s)],masks[key_for(s)])[0].tolist())
        return result
    validation=predictions(val)
    def ledger(partition,preds,threshold):
        return evaluate_ledger([Trade(s.instrument,s.decision_time,s.label_end_time,math.expm1(s.forward_return),
                                     int(p[0]>threshold)-int(p[0]<-threshold)) for s,p in zip(partition,preds)],
                               fee_bps=fee_bps,slippage_bps=slippage_bps)
    threshold=max((0.,.0005,.001,.002),key=lambda t:ledger(val,validation,t)['mean'])
    # The test predictions are requested only after freezing validation choice.
    predictions_test=predictions(test);net=ledger(test,predictions_test,threshold)
    controls=evaluate_controls([s.features for s in train],[s.forward_return for s in train],
                               [s.features for s in test],[s.forward_return for s in test],seed=seed,
                               train_events=[(s.instrument,s.decision_time) for s in train],
                               test_events=[(s.instrument,s.decision_time) for s in test],
                               history_x=[s.features for s in ordered],
                               history_events=[(s.instrument,s.decision_time) for s in ordered])
    metrics=gaussian_scores([p[0] for p in predictions_test],[p[1] for p in predictions_test],[s.forward_return for s in test])
    interval=bootstrap_mean_ci(net['returns'],seed=seed,block_size=min(3,len(test)))
    if cancel():
        raise TrainingCancelled('cancelled before experiment publication')
    dataset_digest=_example_fingerprint((records[k] for k in sorted(records)),cancel)
    if cancel():raise TrainingCancelled('cancelled before experiment publication')
    model_digest=save_checkpoint(model,checkpoint_path,dataset_sha256=train_digest,seed=seed)
    return {'status':'SYNTHETIC_ENGINEERING_ONLY','real_oos':'BLOCKED','seed':seed,'config':asdict(config),
            'research_config':{'train_end':train_end,'validation_end':validation_end,'test_end':test_end,
                               'embargo_ns':embargo_ns,'steps':steps,'fee_bps':fee_bps,'slippage_bps':slippage_bps,
                               'holdout_symbols':sorted(holdout_symbols)},
            'dataset_sha256':dataset_digest,'training_dataset_sha256':train_digest,
            'model_sha256':model_digest,'train_count':len(train),'validation_count':len(val),'test_count':len(test),
            'holdout_count':sum(key_for(s)[2] in holdout_symbols for s in test),'parameters_updated':changed,
            'losses':losses,'threshold':threshold,'controls':controls,'ledger':net,
            'exploratory_ci':interval,'test_metrics':metrics}


def run_walk_forward(examples,checkpoint_dir,folds,*,config=StructuralConfig(),steps=20,seed=0,
                     allow_retraining_on_prior_oos=False,**experiment_options):
    """Fit a fresh structural model per purged fold; never pool overlapping PnL.

    Expanding deployment-style retraining may reuse prior OOS observations only
    by explicit opt-in, and is labelled sequential, not independent holdout.
    Validate ALL temporal windows before publishing any fold's checkpoint.
    """
    from pathlib import Path
    from research.alphafold_training.evaluation import Sample,purged_split
    from research.alphafold_training.gates import assert_no_cross_partition_label_overlap
    integer(seed,'seed');config.validate()
    if type(allow_retraining_on_prior_oos) is not bool:raise ValueError('explicit retraining policy required')
    from itertools import islice
    cancel=experiment_options.get('cancel',lambda:False)
    if cancel():raise TrainingCancelled('cancelled before walk-forward preparation')
    examples=list(islice(examples,1025));folds=list(islice(folds,33))
    if not examples or len(examples)>1024 or not 1<=len(folds)<=32:raise ValueError('walk-forward resource budget')
    _admit_preparation(examples,config,cancel)
    metadata=[]
    for e in examples:
        if cancel():raise TrainingCancelled('cancelled during walk-forward planning')
        e.snapshot.validate();e.target.validate()
        if e.label_end_ns-e.snapshot.origin_ns!=config.horizon_ns:raise ValueError('trained horizon mismatch')
        bars=[b for b in e.snapshot.bars if b.instrument==e.target and b.timeframe_ns==e.timeframe_ns]
        if not bars:raise ValueError('missing target history')
        identity='|'.join((e.target.exchange,e.target.market_type,e.target.symbol,str(e.timeframe_ns)))
        # This actual available close is only temporal-planner metadata. Each
        # fitted fold constructs its complete causal return/volatility tracks.
        metadata.append(Sample(identity,e.snapshot.origin_ns,e.label_end_ns,e.snapshot.origin_ns,(bars[-1].close,),e.forward_log_return))
    embargo=experiment_options.get('embargo_ns',0)
    windows=[];prior_test=[];previous_end=None
    for bounds in folds:
        if cancel():raise TrainingCancelled('cancelled during walk-forward planning')
        if len(bounds)!=3:raise ValueError('fold requires train/validation/test boundaries')
        for boundary in bounds:integer(boundary,'fold boundary',1)
        train,val,test=purged_split(metadata,*bounds,embargo)
        if not train or not val or not test:raise ValueError('nonempty walk-forward partitions required')
        assert_no_cross_partition_label_overlap(train,val,test)
        start=min(s.decision_time for s in test);end=max(s.label_end_time for s in test)
        if previous_end is not None and start<previous_end:raise ValueError('overlapping OOS windows')
        if not allow_retraining_on_prior_oos:
            for row in train+val:
                if any(row.decision_time<p.label_end_time and p.decision_time<row.label_end_time for p in prior_test):
                    raise ValueError('prior OOS cannot enter later train/validation without explicit sequential retraining')
        previous_end=end;prior_test.extend(test);windows.append(bounds)
    root=Path(checkpoint_dir)
    if root.is_symlink() or root.exists() and not root.is_dir():raise ValueError('ordinary checkpoint directory required')
    paths=[root/f'fold-{i:03d}.json' for i in range(len(windows))]
    if any(p.exists() or p.is_symlink() for p in paths):raise ValueError('fold checkpoint exists; refusing replay')
    root.mkdir(parents=True,exist_ok=True)
    reports=[run_experiment(examples,path,train_end=a,validation_end=b,test_end=c,
                            config=config,steps=steps,seed=seed+i,**experiment_options)
             for i,(path,(a,b,c)) in enumerate(zip(paths,windows))]
    return {'status':'SYNTHETIC_ENGINEERING_ONLY','real_oos':'BLOCKED','fold_count':len(reports),'folds':reports,
            'fold_independence':'SEQUENTIAL_RETRAINING' if allow_retraining_on_prior_oos else 'NO_PRIOR_OOS_REUSE',
            'aggregation':'NO_POOLED_PORTFOLIO_CLAIM'}
