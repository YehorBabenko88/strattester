"""Preparation-only local proposal. Never imports/calls Math or grants execution.

Owner source compatibility is not runtime permission. Numeric result validation
checks shape/lineage, NOT correctness, authenticity or actual owner execution.
"""
import hashlib
import json
import math
import re

SOURCE_SHA='0fe1848d0ba8b341c374456817f65ad4f3d86b7833bce3510d509a373b76729a'
SOURCE_HEAD='5721987a15d20c3f9984d52eac4446704566d4b9'
REQUEST_KEYS={'schema','dataset_id','dataset_hash','feature_version','decision_cutoff','transform_source_sha',
              'math_source_head','operation','parameters','unit','semantic_kind','interval_ms','points','missingness'}
POINT_KEYS={'event_start','event_end','availability_timestamp','value'}
RESULT_KEYS={'schema','dataset_id','dataset_hash','feature_version','decision_cutoff','availability_timestamp',
             'transform_source_sha','math_source_head','operation','parameters','input_prefix_hash','request_hash',
             'unit','semantic_kind','values','event_timestamps','availability_timestamps','missingness',
             'math_valid_flags','execution_authority','training_authorized','trading_authorized','output_hash'}
OPERATIONS={'difference':{'order':1},'rolling_volatility':{'window':30}}


def _bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')


def _hash(value):return hashlib.sha256(_bytes(value)).hexdigest()


def _snapshot(value):
    remaining=[30000]
    active=set()
    def visit(v,depth):
        remaining[0]-=1
        if depth>12 or remaining[0]<0:raise ValueError('INERT_BOUNDS')
        if v is None or type(v) is bool:return
        if type(v) is str:
            if len(v)>4096:raise ValueError('TEXT_BOUNDS')
            return
        if type(v) is int:
            if abs(v)>2**53-1:raise ValueError('INTEGER_BOUNDS')
            return
        if type(v) is float:
            if not math.isfinite(v):raise ValueError('FINITE_REQUIRED')
            return
        if type(v) not in (list,dict) or id(v) in active:raise ValueError('PLAIN_BUILTINS_REQUIRED')
        if len(v)>(2000 if type(v) is list else 64):raise ValueError('CONTAINER_BOUNDS')
        active.add(id(v))
        if type(v) is dict:
            for k,x in v.items():
                if type(k) is not str or len(k)>128:raise ValueError('KEY_REQUIRED')
                visit(x,depth+1)
        else:
            for x in v:visit(x,depth+1)
        active.remove(id(v))
    visit(value,0)
    raw=_bytes(value)
    if len(raw)>262144:raise ValueError('BYTE_BOUNDS')
    return json.loads(raw)


def _clock(value):
    if type(value) is not int or not 0<=value<=2**53-1:raise ValueError('CLOCK_REQUIRED')


def _pin(value):
    if type(value) is not str or re.fullmatch('[a-f0-9]{64}',value) is None:raise ValueError('SHA256_REQUIRED')


def _label(value):
    if type(value) is not str or re.fullmatch('[A-Za-z0-9_.:/-]{1,128}',value) is None:raise ValueError('LABEL_REQUIRED')


def prepare_request(request):
    """Freeze inert causal prefix identity; result ALWAYS EXECUTION_BLOCKED."""
    r=_snapshot(request)
    if type(r) is not dict or set(r)!=REQUEST_KEYS or r['schema']!='mwi.math.feature.request.v1':raise ValueError('REQUEST_SCHEMA')
    for k in ('dataset_id','feature_version'):_label(r[k])
    _pin(r['dataset_hash']);_clock(r['decision_cutoff'])
    if r['transform_source_sha']!=SOURCE_SHA or r['math_source_head']!=SOURCE_HEAD:raise ValueError('OWNER_SOURCE_PIN')
    if type(r['operation']) is not str or r['operation'] not in OPERATIONS:raise ValueError('OPERATION_ALLOWLIST')
    if type(r['parameters']) is not dict or r['parameters']!=OPERATIONS[r['operation']] or any(type(v) is not int for v in r['parameters'].values()):raise ValueError('FIXED_PARAMETERS')
    if r['semantic_kind']!='price':raise ValueError('A7_ORIGINAL_PRICES_ONLY')
    if type(r['unit']) is not str or re.fullmatch('[A-Z]{2,12}/[A-Z]{2,12}',r['unit']) is None:raise ValueError('PRICE_UNIT')
    if type(r['interval_ms']) is not int or not 1<=r['interval_ms']<=86400000:raise ValueError('INTERVAL')
    points=r['points'];missing=r['missingness']
    if type(points) is not list or not 2<=len(points)<=2000 or type(missing) is not list or len(points)!=len(missing):raise ValueError('POINT_SHAPE')
    if r['operation']=='difference' and len(points)<2:raise ValueError('DIFFERENCE_WARMUP')
    previous=None
    for point,mask in zip(points,missing):
        if type(point) is not dict or set(point)!=POINT_KEYS or type(mask) is not bool:raise ValueError('POINT_SCHEMA')
        for k in ('event_start','event_end','availability_timestamp'):_clock(point[k])
        lo,hi,available=(point[k] for k in ('event_start','event_end','availability_timestamp'))
        if hi-lo!=r['interval_ms'] or not hi<=available<=r['decision_cutoff'] or previous is not None and lo!=previous:raise ValueError('CAUSAL_CONTIGUOUS_PREFIX')
        previous=hi
        value=point['value']
        if mask:raise ValueError('A7_MISSING_DEPENDENCY')
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e12:raise ValueError('A7_VALUE_BOUNDS')
    prefix={k:r[k] for k in ('unit','semantic_kind','interval_ms','points','missingness')}
    out=dict(schema='mwi.math.feature.preparation.v1',status='EXECUTION_BLOCKED',reason='MATH_RUNTIME_AND_EXECUTION_GRANT_ABSENT',
             request=r,request_hash=_hash({'request':r,'contract_semantics_version':'a7-price-delta-window30-v1'}),input_prefix_hash=_hash(prefix),dataset_id=r['dataset_id'],dataset_hash=r['dataset_hash'],
             feature_version=r['feature_version'],decision_cutoff=r['decision_cutoff'],
             availability_timestamp=max(p['availability_timestamp'] for p in points),
             transform_source_sha=SOURCE_SHA,parameters=r['parameters'],missingness=list(missing),
             math_valid_flags={'input_schema_valid':True,'clock_assertions_causal':True,
                               'mandatory_inputs_present':not any(missing),'numerically_executed':False},
             transform_pipeline=[{'operation':'difference','parameters':{'order':1}}]+([] if r['operation']=='difference' else [{'operation':'rolling_volatility','parameters':{'window':30},'ddof':0}]),
             contract_semantics_version='a7-price-delta-window30-v1',
             numerical_output=None,source_authenticity='NOT_EVALUATED',execution_authority=False,
             training_authorized=False,trading_authorized=False,effects=False)
    out['output_hash']=_hash(out)
    return out


def validate_result(result,prepared):
    """Check an untrusted owner-result claim without computing any transform.

    Acceptance is a local schema/lineage receipt, never proof of numerical truth
    or owner execution. Pending runtime/grant keeps execution blocked.
    """
    p=_snapshot(prepared)
    if type(p) is not dict or 'request' not in p or prepare_request(p['request'])!=p:raise ValueError('PREPARATION_IDENTITY')
    r=_snapshot(result);q=p['request']
    if type(r) is not dict or set(r)!=RESULT_KEYS or r['schema']!='mwi.math.feature.result.v1':raise ValueError('RESULT_SCHEMA')
    _pin(r['output_hash'])
    if _hash({k:v for k,v in r.items() if k!='output_hash'})!=r['output_hash']:raise ValueError('OUTPUT_HASH')
    if type(r['parameters']) is not dict or any(type(v) is not int for v in r['parameters'].values()):raise ValueError('RESULT_PARAMETER_TYPES')
    for k in ('dataset_id','dataset_hash','feature_version','decision_cutoff','transform_source_sha','math_source_head','operation','parameters','unit'):
        if r[k]!=q[k]:raise ValueError('RESULT_LINEAGE')
    if r['input_prefix_hash']!=p['input_prefix_hash'] or r['request_hash']!=p['request_hash']:raise ValueError('PREFIX_IDENTITY')
    if any(r[k] is not False for k in ('execution_authority','training_authorized','trading_authorized')):raise ValueError('AUTHORITY_DENIED')
    if any(q['missingness']):raise ValueError('MISSING_DEPENDENCIES')
    points=q['points'];difference=q['operation']=='difference'
    expected_points=points[1:]
    dependencies=[points[i-1:i+1] for i in range(1,len(points))] if difference else [points[max(0,i-29):i+2] for i in range(len(points)-1)]
    clocks=[max(x['availability_timestamp'] for x in deps) for deps in dependencies]
    if r['event_timestamps']!=[x['event_end'] for x in expected_points] or r['availability_timestamps']!=clocks or r['availability_timestamp']!=max(clocks):raise ValueError('DEPENDENCY_TIMING')
    for x in r['event_timestamps']+r['availability_timestamps']+[r['availability_timestamp']]:_clock(x)
    if type(r['values']) is not list or len(r['values'])!=len(expected_points) or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>2e12 for v in r['values']):raise ValueError('OUTPUT_VALUES')
    if r['missingness']!=[False]*len(expected_points) or any(type(v) is not bool for v in r['missingness']):raise ValueError('OUTPUT_MISSINGNESS')
    ready=difference or len(points)>=31
    if r['math_valid_flags']!={'finite_output':True,'full_window_ready':ready} or any(type(v) is not bool for v in r['math_valid_flags'].values()):raise ValueError('OUTPUT_FLAGS')
    if r['semantic_kind']!=q['operation']:raise ValueError('OUTPUT_SEMANTIC_KIND')
    return dict(schema='mwi.math.result.validation.v1',status='EXECUTION_BLOCKED',result_schema_valid=True,
                numerical_validity_verified=False,source_authenticity='NOT_EVALUATED',output_hash=r['output_hash'],
                warmup_mask=[False]*len(expected_points) if difference else [i<29 for i in range(len(points)-1)],
                execution_authority=False,training_authorized=False,trading_authorized=False)
