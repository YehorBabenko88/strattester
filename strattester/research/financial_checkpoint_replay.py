"""Read-only replay from independently pinned synthetic source/report bytes."""
from dataclasses import fields
from pathlib import Path
from .financial_snapshot import verified_bytes,bounded_json
from .financial_experiment_session import exact
from .financial_walkforward_session import SOURCE_KEYS,_decode,_replay
from .financial_structural_model import StructuralConfig
from .financial_checkpoint import inspect_checkpoint_recovery,load_checkpoint
from .financial_session import check_cancel,bundle_path


def verify_walkforward_replay(source_path,source_sha256,report_path,report_sha256,*,
                              trust_store_path,trust_store_sha256,verifier,cancel=lambda:False):
    """Never fit or resume: reproduce every raw/calibrated test forecast/metric.

    Report pin is external; it authenticates the expected model hashes and
    calibration/threshold state. No digest from an untrusted sibling is adopted.
    Funding-adjusted reports are separate from this model inference check.
    """
    check_cancel(cancel)
    source_path=Path(source_path);report_path=Path(report_path)
    source=exact(bounded_json(verified_bytes(source_path,source_sha256,4*1024*1024)),SOURCE_KEYS)
    report=bounded_json(verified_bytes(report_path,report_sha256,8*1024*1024))
    if (type(source['version']) is not int or source['version']!=1
            or source['scope']!='SYNTHETIC_ENGINEERING_ONLY'
            or source['label_contract']!='PINNED_SYNTHETIC_LOG_RETURNS_V1'
            or report.get('source_sha256')!=source_sha256
            or report.get('status')!='SYNTHETIC_ENGINEERING_ONLY' or report.get('real_oos')!='BLOCKED'):
        raise ValueError('synthetic replay source/report binding')
    config=StructuralConfig(**exact(source['config'],(f.name for f in fields(StructuralConfig)))).validate()
    examples,_=_decode(source_path,source,trust_store_path,trust_store_sha256,verifier,config,cancel)
    folds=report.get('folds')
    if type(folds) is not list or not 1<=len(folds)<=32 or len(folds)!=len(source['folds']):
        raise ValueError('replay fold count')
    recovery=[];count=0
    for i,fold in enumerate(folds):
        check_cancel(cancel)
        path=bundle_path(report_path.parent,f'fold-{i:03d}.json')
        model,metadata=load_checkpoint(path,fold['model_sha256'])
        if model.config!=config or metadata['seed']!=source['seed']+i:
            raise ValueError('replay checkpoint config/seed')
        recovery.append(inspect_checkpoint_recovery(path,fold['model_sha256'],
            dataset_sha256=fold['training_dataset_sha256'],seed=source['seed']+i))
        forecasts=_replay(examples,model,fold['model_sha256'],fold,cancel)
        if forecasts!=fold['forecasts']:raise ValueError('fresh inference forecast mismatch')
        count+=len(forecasts)
    return {'status':'SYNTHETIC_INFERENCE_REPLAY_VERIFIED','source_sha256':source_sha256,
            'report_sha256':report_sha256,'forecasts_verified':count,'folds_verified':len(folds),
            'recovery':recovery,'funding_replay':'SEPARATE_LEDGER_CHECK_REQUIRED',
            'real_oos':'BLOCKED','physical_g1':'NOT_AUTHORIZED','trading':'NO-GO'}
