"""Pinned, signed synthetic snapshots -> fresh training folds -> verified replay.

Dataset labels are explicit synthetic fixtures authenticated by the caller's
dataset pin. Producer signatures authenticate snapshots only. Neither establishes
real market history, deployment latency, funding history or trading authority.
"""
from dataclasses import asdict, fields
from hashlib import sha256
import math
import os
from pathlib import Path
import tempfile
from .financial_contract import Instrument, integer, finite
from .financial_snapshot import bounded_json, verified_bytes, canonical_bytes, reject_linked_path
from .financial_session import bundle_path, check_cancel
from .financial_experiment_session import exact
from .financial_signed_export import ExportPolicy, SourceIdentity, MarketPartition, load_attested_export
from .financial_structural_model import StructuralConfig
from .financial_experiment import Example, run_walk_forward
from .financial_checkpoint import load_checkpoint
from .financial_pipeline import predict_snapshot
from .financial_evaluation import Trade, evaluate_ledger, gaussian_scores

SOURCE_KEYS = {'version', 'scope', 'label_contract', 'exports', 'labels', 'config', 'folds',
               'holdout_symbols', 'steps', 'seed', 'fee_bps', 'slippage_bps', 'embargo_ns',
               'allow_retraining_on_prior_oos'}


def _policy(raw):
    exact(raw, (f.name for f in fields(ExportPolicy)))
    if type(raw['sources']) is not list or type(raw['partitions']) is not list:
        raise ValueError('policy sequence schema')
    sources = tuple(SourceIdentity(**exact(s, (f.name for f in fields(SourceIdentity)))) for s in raw['sources'])
    partitions = tuple(MarketPartition(**exact(p, (f.name for f in fields(MarketPartition)))) for p in raw['partitions'])
    policy = ExportPolicy(**{**raw, 'sources': sources, 'partitions': partitions}).validate()
    if policy.scope != 'SYNTHETIC_ENGINEERING_ONLY':
        raise ValueError('signed walk-forward restricted to synthetic scope')
    return policy


def _decode(path, payload, trust_store_path, trust_store_sha256, verifier, config, cancel):
    exports = payload['exports']; labels = payload['labels']
    if type(exports) is not list or not 1 <= len(exports) <= 64:
        raise ValueError('signed export count budget')
    if type(labels) is not list or not 1 <= len(labels) <= 1024:
        raise ValueError('label count budget')
    snapshots = []; provenance = []; aggregate = 0; previous = -1; first_policy = None
    for row in exports:
        check_cancel(cancel)
        exact(row, {'manifest_path', 'manifest_sha256', 'snapshot_path', 'policy'})
        policy = _policy(row['policy'])
        membership = (policy.producer_id, policy.coherence_epoch_id, policy.sources, policy.partitions)
        if first_policy is None: first_policy = membership
        if membership != first_policy: raise ValueError('inconsistent source/partition/epoch membership')
        if policy.knowledge_cutoff_ns <= previous: raise ValueError('strict chronological export origins required')
        previous = policy.knowledge_cutoff_ns
        # Reserve all serialized objects conservatively before loading a snapshot.
        manifest_path = bundle_path(path.parent, row['manifest_path'])
        manifest = bounded_json(verified_bytes(manifest_path, row['manifest_sha256'], 256*1024))
        integer(manifest.get('snapshot_bytes'), 'snapshot byte budget', 1)
        aggregate += manifest['snapshot_bytes']*16 + 256*1024
        if aggregate + config.max_work_bytes > 512*1024*1024:
            raise ValueError('aggregate signed input budget')
        attested = load_attested_export(manifest_path=manifest_path, manifest_sha256=row['manifest_sha256'],
            snapshot_path=bundle_path(path.parent, row['snapshot_path']), trust_store_path=trust_store_path,
            trust_store_sha256=trust_store_sha256, policy=policy, verifier=verifier, cancel=cancel)
        snapshots.append(attested.snapshot); provenance.append(attested.provenance)
    examples = []; used = set(); seen = set(); total_bars = 0
    for row in labels:
        check_cancel(cancel)
        exact(row, {'export_index', 'target', 'timeframe_ns', 'label_end_ns', 'forward_log_return'})
        index = integer(row['export_index'], 'export index')
        if index >= len(snapshots): raise ValueError('label export index')
        target = Instrument(**exact(row['target'], (f.name for f in fields(Instrument))))
        target.validate()
        tf = integer(row['timeframe_ns'], 'timeframe', 1)
        end = integer(row['label_end_ns'], 'label end', 1)
        label = finite(row['forward_log_return'], 'synthetic label')
        snapshot = snapshots[index]
        if end-snapshot.origin_ns != config.horizon_ns or config.horizon_ns % tf:
            raise ValueError('label horizon mismatch')
        if not any(b.instrument == target and b.timeframe_ns == tf for b in snapshot.bars):
            raise ValueError('label target partition absent')
        key = (index, target, tf)
        if key in seen: raise ValueError('duplicate synthetic label')
        seen.add(key); used.add(index); total_bars += len(snapshot.bars)
        if total_bars > 100_000: raise ValueError('aggregate example bar budget')
        examples.append(Example(snapshot, target, tf, end, label))
    if used != set(range(len(snapshots))): raise ValueError('unused signed export')
    return examples, provenance


def _replay(examples, model, model_sha256, fold, cancel):
    # Use precisely the trainer's purged test membership, after validation froze
    # the threshold; replay never selects a threshold or adjusts model weights.
    bounds = fold['research_config']; test = sorted(
        (e for e in examples if bounds['validation_end'] <= e.snapshot.origin_ns < bounds['test_end']
         and e.label_end_ns <= bounds['test_end']),
        key=lambda e: (e.snapshot.origin_ns, '|'.join((e.target.exchange, e.target.market_type, e.target.symbol, str(e.timeframe_ns)))))
    forecasts = []; trades = []; mus = []; scales = []; labels = []
    for e in test:
        check_cancel(cancel)
        p = predict_snapshot(e.snapshot, model, instrument=e.target, timeframe_ns=e.timeframe_ns,
            horizon_ns=model.config.horizon_ns, model_sha256=model_sha256, available_ns=e.snapshot.origin_ns)
        position = int(p.mu > fold['threshold']) - int(p.mu < -fold['threshold'])
        identity = '|'.join((e.target.exchange, e.target.market_type, e.target.symbol, str(e.timeframe_ns)))
        trades.append(Trade(identity, p.available_ns, e.label_end_ns, math.expm1(e.forward_log_return), position))
        forecasts.append({'prediction': asdict(p), 'timeframe_ns': e.timeframe_ns, 'label_end_ns': e.label_end_ns,
                          'forward_log_return': e.forward_log_return, 'position': position})
        mus.append(p.mu); scales.append(p.scale); labels.append(e.forward_log_return)
    ledger = evaluate_ledger(trades, fee_bps=bounds['fee_bps'], slippage_bps=bounds['slippage_bps'])
    metrics = gaussian_scores(mus, scales, labels)
    if ledger != fold['ledger'] or metrics != fold['test_metrics'] or len(forecasts) != fold['test_count']:
        raise ValueError('verified fold checkpoint replay mismatch')
    return forecasts


def run_walkforward_file(source_path, source_sha256, output_dir, *, trust_store_path, trust_store_sha256,
                         checkpoint_path, checkpoint_sha256, verifier, enable_research=False, cancel=lambda: False):
    check_cancel(cancel)
    if enable_research is not True: raise ValueError('explicit --enable-research required')
    path = Path(source_path)
    data = verified_bytes(path, source_sha256, 4*1024*1024)
    payload = exact(bounded_json(data), SOURCE_KEYS)
    if type(payload['version']) is not int or payload['version'] != 1: raise ValueError('walk-forward version')
    if payload['scope'] != 'SYNTHETIC_ENGINEERING_ONLY' or payload['label_contract'] != 'PINNED_SYNTHETIC_LOG_RETURNS_V1':
        raise ValueError('pinned synthetic label contract required; real OOS blocked')
    config = StructuralConfig(**exact(payload['config'], (f.name for f in fields(StructuralConfig)))).validate()
    integer(payload['steps'], 'steps', 1)
    if payload['steps'] > 1000: raise ValueError('training step budget')
    integer(payload['seed'], 'seed'); integer(payload['embargo_ns'], 'embargo')
    if type(payload['folds']) is not list or not 1 <= len(payload['folds']) <= 32:
        raise ValueError('fold count budget')
    if config.max_work_bytes + len(data)*16 > 512*1024*1024: raise ValueError('aggregate preparation budget')
    target = Path(output_dir); root = reject_linked_path(target.parent)
    if target.exists() or target.is_symlink(): raise ValueError('output exists; refusing overwrite')
    examples, provenance = _decode(path, payload, trust_store_path, trust_store_sha256, verifier, config, cancel)
    check_cancel(cancel)
    bootstrap, metadata = load_checkpoint(checkpoint_path, checkpoint_sha256)
    if bootstrap.config != config: raise ValueError('bootstrap checkpoint configuration mismatch')
    initial = []
    for e in examples:
        check_cancel(cancel)
        initial.append(asdict(predict_snapshot(e.snapshot, bootstrap, instrument=e.target, timeframe_ns=e.timeframe_ns,
            horizon_ns=config.horizon_ns, model_sha256=checkpoint_sha256, available_ns=e.snapshot.origin_ns)))
    del bootstrap
    options = {k: payload[k] for k in ('holdout_symbols', 'steps', 'seed', 'fee_bps', 'slippage_bps', 'embargo_ns', 'allow_retraining_on_prior_oos')}
    check_cancel(cancel)
    with tempfile.TemporaryDirectory(prefix='.walkforward-', dir=root) as temporary:
        stage = Path(temporary)
        result = run_walk_forward(examples, stage, payload['folds'], config=config, cancel=cancel, **options)
        for i, fold in enumerate(result['folds']):
            check_cancel(cancel)
            model, saved = load_checkpoint(stage/f'fold-{i:03d}.json', fold['model_sha256'])
            if saved['dataset_sha256'] != fold['training_dataset_sha256'] or saved['seed'] != payload['seed']+i:
                raise ValueError('fold checkpoint training provenance mismatch')
            fold['forecasts'] = _replay(examples, model, fold['model_sha256'], fold, cancel)
            fold['checkpoint_reloaded'] = True
            del model
        result.update(source_sha256=source_sha256, source_bytes=len(data), signed_exports=provenance,
            bootstrap_checkpoint_sha256=checkpoint_sha256, bootstrap_dataset_sha256=metadata['dataset_sha256'], bootstrap_predictions=initial,
            bootstrap_role='DIAGNOSTIC_ONLY; FRESH_FOLDS_NEVER_WARM_START_FROM_BOOTSTRAP_OR_PRIOR_FOLD',
            label_contract=payload['label_contract'], label_authority='CALLER_PINNED_SYNTHETIC_ONLY_NOT_PRODUCER_ATTESTED',
            preprocessing='CAUSAL_PER_SNAPSHOT_RETURNS_NO_GLOBAL_FIT; BASELINES_FIT_TRAIN_ONLY',
            prediction_availability='SYNTHETIC_ORIGIN_ONLY_NOT_DEPLOYMENT_LATENCY',
            funding={'status':'BLOCKED','reason':'NO_SIGNED_FUNDING_EVENTS','ledger_assumption':'FUNDING_EXCLUDED; NOT_FUNDING_ADJUSTED_PNL'},
            physical_g1='NOT_AUTHORIZED', trading='NO-GO', native_resource_caps='NOT_ENFORCED')
        encoded = canonical_bytes(result)
        if len(encoded) > 8*1024*1024 or sum(p.stat().st_size for p in stage.iterdir())+len(encoded) > 64*1024*1024:
            raise ValueError('walk-forward output byte budget')
        check_cancel(cancel)
        with (stage/'report.json').open('xb') as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        check_cancel(cancel)
        if target.exists() or target.is_symlink(): raise ValueError('output exists; refusing overwrite')
        os.rename(stage, target)
    return {'status':'SYNTHETIC_ENGINEERING_ONLY', 'real_oos':'BLOCKED', 'source_sha256':source_sha256,
            'fold_count':result['fold_count'], 'output':str(target), 'report_sha256':sha256(encoded).hexdigest(),
            'funding':'BLOCKED_NO_EVENT_DATA', 'trading':'NO-GO', 'physical_g1':'NOT_AUTHORIZED', 'native_resource_caps':'NOT_ENFORCED'}
