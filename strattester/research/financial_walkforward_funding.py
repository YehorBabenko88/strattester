"""Explicit signed synthetic funding for post-hoc OOS scoring only."""
from dataclasses import asdict, replace
import math
from .financial_snapshot import bounded_json, verified_bytes
from .financial_session import bundle_path, check_cancel
from .financial_experiment_session import exact
from .financial_authenticated_funding import load_funding_policy, load_authenticated_funding
from .financial_evaluation import Trade, evaluate_ledger


def load_walkforward_funding(path, expected_sha256, examples, verifier, cancel):
    from pathlib import Path
    path=Path(path)
    payload=exact(bounded_json(verified_bytes(path,expected_sha256,256*1024)),
                  {'version','scope','entries'})
    if type(payload['version']) is not int or payload['version']!=1 or payload['scope']!='SYNTHETIC_ENGINEERING_ONLY':
        raise ValueError('synthetic funding bundle required')
    if type(payload['entries']) is not list or not 1<=len(payload['entries'])<=64:
        raise ValueError('funding bundle entry budget')
    expected={(*asdict(e.target).values(),e.timeframe_ns) for e in examples}
    epochs={e.snapshot.coherence_id for e in examples}
    windows={};provenance=[];events=0
    for entry in payload['entries']:
        check_cancel(cancel)
        exact(entry,{'path','sha256','policy_path','policy_sha256','trust_store_path','trust_store_sha256'})
        policy=load_funding_policy(bundle_path(path.parent,entry['policy_path']),entry['policy_sha256'])
        if policy.scope!='SYNTHETIC_ENGINEERING_ONLY' or epochs!={policy.coherence_epoch_id}:
            raise ValueError('funding scope/epoch consistency mismatch')
        key=(*asdict(policy.instrument).values(),policy.timeframe_ns)
        if key not in expected or key in windows:
            raise ValueError('funding partition/timeframe duplicate or mismatch')
        verified=load_authenticated_funding(path=bundle_path(path.parent,entry['path']),
            expected_sha256=entry['sha256'],policy=policy,verifier=verifier,cancel=cancel,
            trust_store_path=bundle_path(path.parent,entry['trust_store_path']),
            trust_store_sha256=entry['trust_store_sha256'])
        events+=len(verified.window.events)
        if events>10000:raise ValueError('aggregate funding event budget')
        # Join through the exact typed partition, not string replacement/symbol.
        identity='|'.join(map(str,key))
        windows[key]=replace(verified.window,instrument=identity,
            events=tuple(replace(e,instrument=identity) for e in verified.window.events))
        provenance.append({**verified.provenance,'policy_bytes_sha256':entry['policy_sha256']})
    if set(windows)!=expected:raise ValueError('BLOCKED: incomplete funding partition coverage')
    return windows, {'status':'SIGNED_SYNTHETIC_ONLY','bundle_sha256':expected_sha256,
        'historical_truth':'NOT_ESTABLISHED_BY_SIGNATURE',
        'epoch_binding':'SYNTHETIC_CONSISTENCY_ONLY_NOT_COHERENT_PRODUCER_PROOF',
        'usage':'POSTHOC_TEST_SCORING_ONLY_NO_MODEL_OR_THRESHOLD_SELECTION',
        'runtime_funding_admission':'NOT_ENABLED','sources':provenance}


def score_funding(forecasts, windows, bounds):
    trades=[];used={}
    for row in forecasts:
        p=row['prediction']
        # Prediction dictionaries can originate from canonical sorted JSON;
        # field ordering is never an identity contract.
        i=p['instrument'];key=(i['exchange'],i['market_type'],i['symbol'],row['timeframe_ns'])
        used[key]=windows[key]
        trades.append(Trade('|'.join(map(str,key)),p['available_ns'],row['label_end_ns'],
                            math.expm1(row['forward_log_return']),row['position']))
    result=evaluate_ledger(trades,fee_bps=bounds['fee_bps'],slippage_bps=bounds['slippage_bps'],
                           funding_windows=tuple(used.values()))
    result['funding_status']='PINNED_SIGNATURE_VERIFIED_SYNTHETIC_ONLY_HISTORY_UNPROVEN'
    return result


def score_control_funding(ledger, windows, bounds):
    """Identical signed settlements/costs for each frozen control strategy."""
    by_identity={window.instrument:window for window in windows.values()}
    if len(by_identity) != len(windows):
        raise ValueError('funding identity collision')
    used={row['instrument'] for row in ledger['rows']}
    trades=[Trade(row['instrument'],row['start_ns'],row['end_ns'],
                  row['gross_return']/row['position'] if row['position'] else 0.,row['position'])
            for row in ledger['rows']]
    result=evaluate_ledger(trades,fee_bps=bounds['fee_bps'],slippage_bps=bounds['slippage_bps'],
                           funding_windows=tuple(by_identity[key] for key in sorted(used)))
    result['funding_status']='PINNED_SIGNATURE_VERIFIED_SYNTHETIC_ONLY_HISTORY_UNPROVEN'
    return result
