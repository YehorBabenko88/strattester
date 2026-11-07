from __future__ import annotations
from dataclasses import asdict,is_dataclass
import hashlib,json,re

def _metrics(m):
    if is_dataclass(m): d=asdict(m)
    else:
        keys=('trades','wins','losses','win_rate','gross_pnl','net_pnl','fees','expectancy','profit_factor',
              'max_drawdown','avg_mae','avg_mfe','avg_r_multiple','avg_holding_ms','max_consecutive_losses')
        d={k:getattr(m,k) for k in keys if hasattr(m,k)}
    return d

def persist_report(store,run_id,symbol,strategy_result,report):
    metrics=_metrics(report.primary)
    metrics['fingerprint']=strategy_result.fingerprint
    metrics['coverage']='COMPLETE_HISTORY'
    store.put(run_id,symbol,strategy_result.strategy_id,strategy_result.strategy_version,metrics)
    return metrics


def persist_report_fenced(store,stage_id,run_id,symbol,strategy_result,report,lease_validator,job_id=None,lease_token=0,node_generation=0):
    """Persist scientific output without allowing a stale worker to publish it."""
    metrics=_metrics(report.primary)
    metrics['fingerprint']=strategy_result.fingerprint
    metrics['coverage']='COMPLETE_HISTORY'
    store.stage(stage_id,run_id,symbol,strategy_result.strategy_id,strategy_result.strategy_version,metrics,job_id=job_id,lease_token=lease_token,node_generation=node_generation)
    if not store.promote(stage_id,lease_validator):
        raise RuntimeError('result publication fenced: execution authority is no longer valid')
    return metrics

def stage_gateway_research_artifact(store,stage_id,run_id,symbol,operation_id,operation_revision,raw_descriptor,artifact_bytes,*,original_intent_sha256):
    """Stage local exact bytes only. No semantic/source/authority admission.

    The combined bound is a necessary lower bound on A4's total closure budget;
    A4 must still bound all retained request/schema/dependency bytes separately.
    Caller retains the original artifact bytes. No store publication is attempted.
    """
    for raw,limit in ((raw_descriptor,65536),(artifact_bytes,1048576)):
        if type(raw) is not bytes or not 0<len(raw)<=limit:raise ValueError('ARTIFACT_STAGE_INVALID')
    if len(raw_descriptor)+len(artifact_bytes)>1048576:raise ValueError('ARTIFACT_STAGE_INVALID')
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('ARTIFACT_STAGE_INVALID')
            value[key]=item
        return value
    def constant(_):raise ValueError('ARTIFACT_STAGE_INVALID')
    try:
        descriptor=json.loads(raw_descriptor.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
        artifact=json.loads(artifact_bytes.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
        if type(descriptor) is not dict or type(artifact) is not dict:raise ValueError('ARTIFACT_STAGE_INVALID')
        allowed={'stratt.gateway.synthetic.research.result.v1-review1','stratt.gateway.synthetic.research.result.v2-review1'}
        if descriptor.get('schema') not in allowed:raise ValueError('ARTIFACT_STAGE_INVALID')
        fields={'schema','state','scope','experiment','request_raw_sha256','artifact','provenance','clocks','series_semantics','financial','execution_authority','trading_authorized','training_authorized','production_runtime_admission'}
        if descriptor['schema']=='stratt.gateway.synthetic.research.result.v2-review1':fields.add('upstream_binding')
        if set(descriptor)!=fields:raise ValueError('ARTIFACT_STAGE_INVALID')
        if descriptor['state']!='COMPUTED_TEST_ONLY' or descriptor['scope']!='TEST_ONLY_SYNTHETIC' or descriptor['production_runtime_admission']!='BLOCKED':raise ValueError('ARTIFACT_STAGE_INVALID')
        for value in (descriptor,artifact):
            for key in ('execution_authority','trading_authorized','training_authorized'):
                if value.get(key) is not False:raise ValueError('ARTIFACT_STAGE_INVALID')
        expected_financial=dict(status='UNAVAILABLE_NUMERICAL_PROFILE_NONE',gross_pnl=None,net_pnl=None,fees=None,slippage=None,signed_funding=None,currency=None,scale=None,calculation_basis='NOT_CALCULATED')
        if descriptor['financial']!=expected_financial:raise ValueError('ARTIFACT_STAGE_INVALID')
        binding=descriptor['artifact']
        if type(binding) is not dict or set(binding)!={'schema','encoding','byte_count','raw_sha256'}:raise ValueError('ARTIFACT_STAGE_INVALID')
        if binding['schema']!='meta.ohlcv.research.result.v1' or binding['encoding']!='JSON_UTF8_CANONICAL_META_V1_NOT_C3':raise ValueError('ARTIFACT_STAGE_INVALID')
        if type(binding['byte_count']) is not str or binding['byte_count']!=str(len(artifact_bytes)):raise ValueError('ARTIFACT_STAGE_INVALID')
        if type(binding['raw_sha256']) is not str or re.fullmatch(r'[0-9a-f]{64}',binding['raw_sha256']) is None:raise ValueError('ARTIFACT_STAGE_INVALID')
        if binding['raw_sha256']!=hashlib.sha256(artifact_bytes).hexdigest():raise ValueError('ARTIFACT_STAGE_INVALID')
        if artifact.get('schema')!='meta.ohlcv.research.result.v1' or artifact.get('evidence_class')!='SYNTHETIC' or artifact.get('symbol')!=symbol or operation_id!='meta.ohlcv.untouched_levels.v1':raise ValueError('ARTIFACT_STAGE_INVALID')
    except (KeyError,TypeError,UnicodeError,RecursionError,OverflowError):raise ValueError('ARTIFACT_STAGE_INVALID') from None
    store.stage_gateway_artifact(stage_id,run_id,symbol,operation_id,operation_revision,raw_descriptor,artifact_sha256=binding['raw_sha256'],original_intent_sha256=original_intent_sha256)
    return None
