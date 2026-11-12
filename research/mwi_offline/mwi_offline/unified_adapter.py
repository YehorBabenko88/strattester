"""Inert compatibility preparation for Unified; no owner imports or API calls."""
import hashlib
import json
import math
import re
from .strategy import validate


def _plain(value,depth=0,budget=None):
    if budget is None:budget=[0]
    budget[0]+=1
    if depth>12 or budget[0]>2048:raise ValueError('PREPARATION_BOUNDS')
    t=type(value)
    if value is None or t in (bool,int):return
    if t is float and math.isfinite(value):return
    if t is str and len(value)<=4096:return
    if t is list and len(value)<=64:
        for v in value:_plain(v,depth+1,budget)
        return
    if t is dict and len(value)<=64:
        for k,v in value.items():
            if type(k) is not str or len(k)>128:raise ValueError('PREPARATION_KEYS')
            _plain(v,depth+1,budget)
        return
    raise ValueError('BOUNDED_PLAIN_DATA_REQUIRED')


def _hash(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>65536:raise ValueError('PREPARATION_BYTES')
    return hashlib.sha256(raw).hexdigest()


def _sha(value,length):
    if type(value) is not str or re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is None:
        raise ValueError('SOURCE_OR_ARTIFACT_HASH')


def prepare_unified(candidate,*,strategy_source_sha=None):
    """Report mappings only; never emits an accepted owner plan or experiment ID.

    A supplied 40-hex revision is caller context, not authenticated source. The
    synthetic cost/model contract cannot meet signed funding/Math prerequisites.
    """
    _plain(candidate);validate(candidate)
    if strategy_source_sha is not None:_sha(strategy_source_sha,40)
    blockers=['DATASET_AND_SOURCE_NOT_ADMITTED','SOURCE_SIGNED_FUNDING_UNAVAILABLE',
              'MATH_OWNER_CONFIGURATION_UNAVAILABLE','QUERY_AND_PERIODS_UNAVAILABLE',
              'OWNER_RESOURCE_ADMISSION_UNAVAILABLE','OWNER_SCOPE_PENDING']
    if strategy_source_sha is None:blockers.append('STRATEGY_SOURCE_REVISION_UNAVAILABLE')
    result=dict(schema='mwi.local.unified-preparation.v1',status='PREPARATION_BLOCKED',
        owner_operation='prepare_research_plan',operation_kind='PURE_PREPARATION',
        owner_schema='unified.gateway.research-plan.v1',endpoint=None,owner_plan=None,
        local_candidate_id=candidate['strategy_id'],local_dataset_id=candidate['dataset_id'],
        local_model_hash=candidate['model_hash'],strategy_source_sha=strategy_source_sha,
        source_context='UNKNOWN' if strategy_source_sha is None else 'CALLER_SUPPLIED_NOT_AUTHENTICATED',
        evidence_class='SYNTHETIC',publication_status='LOCAL_UNATTESTED',
        requested_mode=candidate['mode'],owner_required_execution_model='PAPER_ONLY',
        funding=candidate['execution']['funding'],owner_required_funding='SOURCE_SIGNED_SEPARATE',
        declared_local_costs=dict(candidate['execution']),
        job_id=None,experiment_id=None,lease=None,fencing_token=None,
        source_admitted=False,submitted=False,authenticated=False,effects_authorized=False,
        public_submit=False,public_submit_policy='DENY',blockers=blockers)
    result['preparation_sha256']=_hash(result)
    return result
