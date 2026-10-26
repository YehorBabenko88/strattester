"""Externally pinned research sessions; imports never activate a strategy."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from .financial_snapshot import bounded_json,verified_bytes,reject_linked_path
from .financial_contract import Instrument,integer
from .financial_attested_inference import AttestedInferenceRequest
from .financial_signed_export import ExportPolicy,SourceIdentity,MarketPartition
from .financial_training import TrainingCancelled

@dataclass(frozen=True)
class ResearchSession:
    request: AttestedInferenceRequest
    policy: ExportPolicy
    verifier: object
    config_sha256: str
    max_work_bytes: int

def check_cancel(cancel):
    if cancel():raise TrainingCancelled('cancelled research session')

def bundle_path(root,name):
    if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}',name) or name.endswith('.'):
        raise ValueError('ordinary relative bundle path required')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(10)],*[f'LPT{i}' for i in range(10)]}:
        raise ValueError('reserved bundle path')
    return reject_linked_path(root/name)

def load_session(config_path,expected_config_sha256,*,trust_store_sha256,verifier):
    path=Path(config_path)
    p=bounded_json(verified_bytes(path,expected_config_sha256,64*1024))
    required={'version','manifest_path','manifest_sha256','snapshot_path','checkpoint_path','checkpoint_sha256','trust_store_path','instrument','timeframe_ns','horizon_ns','available_ns','policy','max_work_bytes'}
    if set(p)!=required or type(p['version']) is not int or p['version']!=1:raise ValueError('session schema')
    paths={k:bundle_path(path.parent,p[k]) for k in ('manifest_path','snapshot_path','checkpoint_path','trust_store_path')}
    try:
        raw=p['policy'];policy=ExportPolicy(**{**raw,'sources':tuple(SourceIdentity(**s) for s in raw['sources']),'partitions':tuple(MarketPartition(**s) for s in raw['partitions'])}).validate()
        request=AttestedInferenceRequest(**paths,manifest_sha256=p['manifest_sha256'],checkpoint_sha256=p['checkpoint_sha256'],trust_store_sha256=trust_store_sha256,instrument=Instrument(**p['instrument']),timeframe_ns=p['timeframe_ns'],horizon_ns=p['horizon_ns'],available_ns=p['available_ns']).validate()
    except (TypeError,KeyError) as exc:raise ValueError('session typed schema') from exc
    integer(p['max_work_bytes'],'session work budget',1)
    if not 16*1024*1024<=p['max_work_bytes']<=1024*1024*1024:raise ValueError('session work budget')
    return ResearchSession(request,policy,verifier,expected_config_sha256,p['max_work_bytes'])

def verify_session(session,*,cancel=lambda:False):
    from .financial_attested_inference import run_attested_offline
    check_cancel(cancel)
    verified=run_attested_offline(session.request,policy=session.policy,verifier=session.verifier,max_work_bytes=session.max_work_bytes,cancel=cancel)
    check_cancel(cancel)
    return {**verified.provenance,'config_sha256':session.config_sha256,'native_resource_caps':'NOT_ENFORCED'}

def run_session(session,*,enable_research=False,mode='offline',cancel=lambda:False,output_root=None,connected_profile=None,connected_output=None,export_metadata=None,sign_public_fixture=False):
    check_cancel(cancel)
    if enable_research is not True:raise ValueError('explicit --enable-research required')
    if mode not in ('offline','connected'):raise ValueError('research mode')
    if mode=='offline' and (sign_public_fixture or any(x is not None for x in (connected_profile,connected_output,export_metadata))):raise ValueError('offline mode denies connected capabilities')
    if mode=='connected':
        from .financial_grid_exporter import HistoryProfile,export_history
        if type(connected_profile) is not HistoryProfile or connected_output is None or type(export_metadata) is not dict:
            raise ValueError('BLOCKED: explicit qualified connected profile and export metadata required')
        if connected_profile.kind!='SEALED_VERSIONED_HISTORY_V1':
            from .grid_producer_readiness import require_native_grid_export
            require_native_grid_export()
        if sign_public_fixture and (connected_profile.scope!='SYNTHETIC_ENGINEERING_ONLY' or export_metadata.get('producer_id')!='fixture-grid' or export_metadata.get('key_id')!='rfc-key'):
            raise ValueError('public fixture signer restricted to synthetic fixture-grid/rfc-key')
        artifact=export_history(connected_profile,connected_output,cancel=cancel,**export_metadata)
        check_cancel(cancel)
        if sign_public_fixture:
            from dataclasses import replace
            from .financial_grid_exporter import sign_rfc_test_export
            check_cancel(cancel)
            manifest,manifest_sha=sign_rfc_test_export(artifact,openssl_executable=session.verifier.executable,openssl_sha256=session.verifier.executable_sha256,scratch_root=session.verifier.scratch_root)
            check_cancel(cancel)
            derived=replace(session,request=replace(session.request,manifest_path=manifest,manifest_sha256=manifest_sha,snapshot_path=artifact.directory/'snapshot.json'))
            result=run_session(derived,enable_research=True,cancel=cancel)
            result['mode']='CONNECTED_SYNTHETIC_ENGINEERING_ONLY'
            result['provenance'].update(connected_export_sha256=artifact.provenance_sha256,public_fixture_signature=True)
            check_cancel(cancel)
            if output_root is not None:_publish(result,output_root,cancel)
            return result
        return {'mode':'CONNECTED_RESEARCH_ONLY','status':'AWAITING_PRODUCER_SIGNATURE','unsigned_manifest_sha256':artifact.unsigned_manifest_sha256,'snapshot_sha256':artifact.snapshot_sha256,'provenance_sha256':artifact.provenance_sha256,'config_sha256':session.config_sha256,'trading':'NO-GO','physical_g1':'NOT_AUTHORIZED','native_resource_caps':'NOT_ENFORCED'}
    from strattester.strategies.registry import StrategyRegistry
    from strattester.strategies.builtin.financial_structural import register_financial_research,execute_financial_research,FinancialResearchContext
    registry=StrategyRegistry();definition=register_financial_research(registry,research_only=True)
    registry.set_enabled(definition.id,definition.version,True)
    context=FinancialResearchContext(session.request,session.policy,session.verifier,session.max_work_bytes,cancel)
    check_cancel(cancel)
    result=execute_financial_research(registry,context,research_only=True).output
    result['provenance'].update(config_sha256=session.config_sha256,native_resource_caps='NOT_ENFORCED')
    check_cancel(cancel)
    if output_root is not None:_publish(result,output_root,cancel)
    return result

def _publish(result,output_root,cancel):
    from .financial_offline_jobs import publish_result
    from .financial_snapshot import canonical_bytes
    check_cancel(cancel)
    identity=sha256(canonical_bytes(result)).hexdigest()
    result['publication']=publish_result(output_root,identity,result)
