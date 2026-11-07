"""Bounded TEST_ONLY synthetic calculation through existing pinned Meta code.

No submission, storage, ledger, signature substitute, native bootstrap or runtime
admission. Cancellation only discards local output; A5 owns commit-time fencing.
"""
from __future__ import annotations
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import types
import uuid

REQUEST_SCHEMA='stratt.gateway.synthetic.research.request.v1-review1'
RESULT_SCHEMA='stratt.gateway.synthetic.research.result.v1-review1'
OPERATION='meta.ohlcv.untouched_levels.v1'
META_HEAD='f3c01a23fa5baaeeeb28eb8e9397e72b5ef4d5a1'
META_TREE='c155c935a801fa98b7c78219c9798ce1f1be8848'
MAX_REQUEST_BYTES=131072
MAX_RESULT_BYTES=1048576
MAX_ROWS=256
MAX_LEVELS=512
MAX_CLOCK=2**53-1
SOURCE_PINS={'__init__.py':'70d2201e97a9d8b57973b8328ce7e2938e85096035a867aab8b37b35ee1e1883','core.py':'caa15e51394d3c204ecbcf557cd13ce7a6853b5c8005c4d266971f3f14177170','ohlcv_research_adapter.py':'39b165c945f4d5c00fdf96c460d9bf4e34a32c9cb30483d9be6d88f45403a90f'}
_SHADOW_NAMES={'copy.py','dataclasses.py','datetime.py','decimal.py','collections.py','hashlib.py','json.py','math.py','re.py','time.py','sys.py'}
_META_FIELDS=frozenset(('schema','mode','venue','market_type','symbol','timeframe','units','evidence_class','source','dataset_id','request_digest','decision_ms','snapshot_as_of_ms','window_start_ms','window_end_ms','data_available_at_ms','calculated_at_ms','rows','levels','quality_status','coverage_status','source_authenticity','clock_assumptions','missing_capabilities','execution_authority','trading_authorized','training_authorized','h_b_eligible'))

class GatewayResearchError(ValueError):
    """Closed local error code, never a raw source path or authority decision."""
    def __init__(self,code):
        self.code=code
        super().__init__(code)

class GatewayResearchCancelled(GatewayResearchError):
    def __init__(self):super().__init__('CANCELLED')

def _need(condition,code):
    if not condition:raise GatewayResearchError(code)

def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def _closed(value,fields,code):_need(type(value) is dict and set(value)==set(fields),code)
def _clock(value):_need(type(value) is int and 0<=value<=MAX_CLOCK,'INVALID_REQUEST')

def _cancel(check):
    _need(callable(check) and not inspect.iscoroutinefunction(check) and not inspect.iscoroutinefunction(getattr(check,'__call__',None)),'INVALID_CANCEL_CHECK')
    try:value=check()
    except Exception:raise GatewayResearchError('CANCEL_CHECK_FAILED') from None
    if type(value) is not bool:
        # The actual creator owns disposal; refusal never awaits/closes/cancels it.
        raise GatewayResearchError('INVALID_CANCEL_CHECK')
    if value:raise GatewayResearchCancelled()

def _unique(pairs):
    result={}
    for key,value in pairs:
        _need(key not in result,'INVALID_REQUEST');result[key]=value
    return result

def _json_constant(_):raise GatewayResearchError('INVALID_REQUEST')

def _bounded_tree(value):
    stack=[(value,0)];nodes=0
    while stack:
        item,depth=stack.pop();nodes+=1
        _need(nodes<=8192 and depth<=16,'INVALID_REQUEST')
        if type(item) is dict:
            _need(len(item)<=64 and all(type(k) is str and len(k)<=128 for k in item),'INVALID_REQUEST')
            stack.extend((x,depth+1) for x in item.values())
        elif type(item) is list:
            _need(len(item)<=512,'INVALID_REQUEST');stack.extend((x,depth+1) for x in item)
        elif type(item) is str:_need(len(item)<=256,'INVALID_REQUEST')
        elif type(item) is float:_need(math.isfinite(item),'INVALID_REQUEST')
        else:_need(item is None or type(item) in (bool,int),'INVALID_REQUEST')

def _request(raw):
    _need(type(raw) is bytes and 0<len(raw)<=MAX_REQUEST_BYTES and not raw.startswith(b'\xef\xbb\xbf'),'INVALID_REQUEST')
    raw_digest=_sha(raw)
    try:q=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique,parse_constant=_json_constant)
    except GatewayResearchError:raise
    except (ValueError,TypeError,UnicodeError,RecursionError,OverflowError):raise GatewayResearchError('INVALID_REQUEST') from None
    _bounded_tree(q)
    _closed(q,('schema','operation','experiment','payload','decision_ms','analysis_now_ms'),'INVALID_REQUEST')
    _need(q['schema']==REQUEST_SCHEMA,'UNSUPPORTED_SCHEMA')
    _need(q['operation']==OPERATION,'UNSUPPORTED_OPERATION')
    _closed(q['experiment'],('id','revision'),'INVALID_REQUEST')
    code=q['experiment']['id'];revision=q['experiment']['revision']
    _need(type(code) is str and len(code)<=128 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+-]*',code) is not None,'INVALID_REQUEST')
    _need(type(revision) is str and len(revision)<=19 and re.fullmatch(r'0|[1-9][0-9]*',revision) is not None and int(revision)<=2**63-1,'INVALID_REQUEST')
    _clock(q['decision_ms']);_clock(q['analysis_now_ms'])
    _need(type(q['payload']) is dict,'INVALID_REQUEST')
    _need(q['payload'].get('evidence_class')=='SYNTHETIC','NON_SYNTHETIC')
    rows=q['payload'].get('rows')
    _need(type(rows) is list and 1<=len(rows)<=MAX_ROWS,'INVALID_REQUEST')
    return q,raw_digest

def _directory(path):
    info=path.lstat()
    _need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and not (getattr(info,'st_file_attributes',0)&1024),'SOURCE_UNAVAILABLE')

def _source_package(value):
    _need(type(value) is str and 0<len(value)<=4096 and not any(c in value for c in ('\0','\n','\r')),'SOURCE_UNAVAILABLE')
    _need(not value.startswith(('\\\\','//')) and '..' not in re.split(r'[\\/]',value),'SOURCE_UNAVAILABLE')
    root=Path(value)
    _need(root.is_absolute(),'SOURCE_UNAVAILABLE')
    try:
        for parent in reversed(root.parents):_directory(parent)
        for path in (root,root/'src',root/'src/meta_analyse'):_directory(path)
        _need(root.resolve()==root.absolute(),'SOURCE_UNAVAILABLE')
        package=root/'src/meta_analyse'
        for entry in package.iterdir():
            _need(entry.name not in _SHADOW_NAMES and entry.name!='__pycache__' and entry.suffix not in ('.pyc','.pyo'),'SOURCE_UNAVAILABLE')
        return package
    except GatewayResearchError:raise
    except (OSError,ValueError,RuntimeError):raise GatewayResearchError('SOURCE_UNAVAILABLE') from None

def _source_bytes(package):
    found={}
    try:
        for name,pin in SOURCE_PINS.items():
            path=package/name;before=path.lstat()
            _need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and not (getattr(before,'st_file_attributes',0)&1024) and before.st_size<=1048576,'SOURCE_UNAVAILABLE')
            with path.open('rb') as stream:
                opened=os.fstat(stream.fileno())
                _need((opened.st_dev,opened.st_ino)==(before.st_dev,before.st_ino) and opened.st_nlink==1,'SOURCE_UNAVAILABLE')
                raw=stream.read(1048577);after=os.fstat(stream.fileno())
            _need((opened.st_size,opened.st_mtime_ns)==(after.st_size,after.st_mtime_ns) and _sha(raw)==pin,'SOURCE_UNAVAILABLE')
            found[name]=raw
    except GatewayResearchError:raise
    except (OSError,ValueError):raise GatewayResearchError('SOURCE_UNAVAILABLE') from None
    return found

def _actual_meta(q,package,data):
    # All three files were verified before executing even the inert __init__.
    _need(not any(name=='meta_analyse' or name.startswith('meta_analyse.') for name in sys.modules),'SOURCE_UNAVAILABLE')
    prefix='_stratt_gateway_meta_'+uuid.uuid4().hex
    names=(prefix,prefix+'.core',prefix+'.ohlcv_research_adapter')
    _need(not any(name in sys.modules for name in names),'SOURCE_UNAVAILABLE')
    created=[]
    try:
        for name,file in zip(names,('__init__.py','core.py','ohlcv_research_adapter.py')):
            module=types.ModuleType(name);module.__file__=str(package/file);module.__package__=prefix
            if file=='__init__.py':module.__path__=[str(package)]
            sys.modules[name]=module;created.append(name)
            exec(compile(data[file],str(package/file),'exec'),module.__dict__)
        return sys.modules[names[-1]].analyze_ohlcv_research(copy.deepcopy(q['payload']),decision_ms=q['decision_ms'],now_ms=q['analysis_now_ms'])
    except GatewayResearchError:raise
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError,UnicodeError):raise GatewayResearchError('INVALID_OHLCV') from None
    finally:
        for name in reversed(created):sys.modules.pop(name,None)

def _result(value,q):
    _closed(value,_META_FIELDS,'RESULT_UNAVAILABLE')
    _need(value['schema']=='meta.ohlcv.research.result.v1' and value['mode']=='HISTORICAL_RESEARCH' and value['evidence_class']=='SYNTHETIC','RESULT_UNAVAILABLE')
    p=q['payload']
    for key in ('venue','market_type','symbol','timeframe','units','source','dataset_id','rows'):_need(value[key]==p[key],'RESULT_UNAVAILABLE')
    _need(value['request_digest']==_sha(_canonical({'payload':p,'decision_ms':q['decision_ms']})),'RESULT_UNAVAILABLE')
    expected={'decision_ms':q['decision_ms'],'calculated_at_ms':q['analysis_now_ms'],'snapshot_as_of_ms':p['as_of_ms'],'window_start_ms':p['start_ms'],'window_end_ms':p['end_ms'],'data_available_at_ms':p['source']['retrieved_at_ms']}
    for key,clock in expected.items():_clock(value[key]);_need(value[key]==clock,'RESULT_UNAVAILABLE')
    for key in ('execution_authority','trading_authorized','training_authorized','h_b_eligible'):_need(value[key] is False,'RESULT_UNAVAILABLE')
    _need(value['quality_status']=='UNKNOWN' and value['coverage_status']=='DECLARED_COMPLETE_UNVERIFIED' and value['source_authenticity']=='NOT_EVALUATED','RESULT_UNAVAILABLE')
    _closed(value['clock_assumptions'],('availability_policy','historical_observation_times','bar_clock','analysis_clock'),'RESULT_UNAVAILABLE')
    _need(value['clock_assumptions']=={'availability_policy':'WHOLE_BACKFILL_AVAILABLE_AT_DECLARED_RETRIEVAL','historical_observation_times':'NOT_PROVIDED','bar_clock':'DECLARED_UTC_MINUTE_BOUNDARIES','analysis_clock':'CALCULATED_NOW_NOT_HISTORICAL_OBSERVATION'},'RESULT_UNAVAILABLE')
    _need(type(value['missing_capabilities']) is list and len(value['missing_capabilities'])<=32 and all(type(x) is str and len(x)<=128 for x in value['missing_capabilities']),'RESULT_UNAVAILABLE')
    levels=value['levels'];_need(type(levels) is list and len(levels)<=MAX_LEVELS,'RESULT_UNAVAILABLE')
    rows={r['event_start_ms']:r for r in p['rows']};seen=set()
    for level in levels:
        _closed(level,('price','kind','timeframe','source_start_ms'),'RESULT_UNAVAILABLE')
        price=level['price'];kind=level['kind'];clock=level['source_start_ms']
        _need(type(price) is str and len(price)<=64 and re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:E[+-]?[0-9]{1,3})?',price) is not None,'RESULT_UNAVAILABLE')
        try:number=Decimal(price)
        except InvalidOperation:raise GatewayResearchError('RESULT_UNAVAILABLE') from None
        _need(number.is_finite() and 0<number<=Decimal('1e15') and kind in ('high','low') and level['timeframe']=='1m','RESULT_UNAVAILABLE')
        _need(type(clock) is int and clock in rows and number==Decimal(str(rows[clock][kind])),'RESULT_UNAVAILABLE')
        _need((kind,number) not in seen,'RESULT_UNAVAILABLE');seen.add((kind,number))
    try:raw=_canonical(value)
    except (ValueError,TypeError,OverflowError,RecursionError):raise GatewayResearchError('RESULT_UNAVAILABLE') from None
    _need(len(raw)<=MAX_RESULT_BYTES,'RESULT_UNAVAILABLE')
    return raw

def execute_synthetic_research(request_bytes,*,meta_source_root,cancel_check):
    """Return {'descriptor': dict, 'artifact_bytes': bytes}; no publication.

    This v1 local fixture codec has no upstream A3 query binding. It must not be
    silently used as that bridge. Source checks do not qualify Meta/native/host.
    """
    _cancel(cancel_check)
    q,request_digest=_request(request_bytes)
    package=_source_package(meta_source_root);data=_source_bytes(package)
    _cancel(cancel_check)
    value=_actual_meta(q,package,data)
    _cancel(cancel_check)
    _need(_source_bytes(_source_package(meta_source_root))==data,'SOURCE_UNAVAILABLE')
    raw=_result(value,q)
    descriptor={'schema':RESULT_SCHEMA,'state':'COMPUTED_TEST_ONLY','scope':'TEST_ONLY_SYNTHETIC','experiment':copy.deepcopy(q['experiment']),'request_raw_sha256':request_digest,
        'artifact':{'schema':value['schema'],'encoding':'JSON_UTF8_CANONICAL_META_V1_NOT_C3','byte_count':str(len(raw)),'raw_sha256':_sha(raw)},
        'provenance':{'stratt_base_head':'072d22214136148b47e82d21fec9e269bd7468ac','stratt_base_tree':'ffaff34af5375b23235491d92a250ccb66eb03df','meta_head':META_HEAD,'meta_tree':META_TREE,'meta_source_sha256':dict(SOURCE_PINS),'dataset_id':value['dataset_id'],'meta_request_digest':value['request_digest'],'dataset_revision':'UNAVAILABLE_A4_BINDING_PENDING','input_units':copy.deepcopy(value['units']),'fidelity':'SYNTHETIC_ENGINEERING_ONLY_NOT_MEASURED','simulation':'NO_ORDERS_NO_LEDGER_NO_EXECUTION_SIGNALS','source_authenticity':'NOT_EVALUATED','availability':'WHOLE_BACKFILL_AT_DECLARED_RETRIEVAL_NOT_HISTORICAL_PIT'},
        'clocks':{key:str(value[key]) for key in ('decision_ms','calculated_at_ms','snapshot_as_of_ms','window_start_ms','window_end_ms','data_available_at_ms')},
        'series_semantics':{'rows':'INPUT_REPLAY_NOT_DERIVED','levels':'ACTUALLY_COMPUTED_WHOLE_WINDOW_LEVELS_NOT_HISTORICAL_SIGNALS'},
        'financial':{'status':'UNAVAILABLE_NUMERICAL_PROFILE_NONE','gross_pnl':None,'net_pnl':None,'fees':None,'slippage':None,'signed_funding':None,'currency':None,'scale':None,'calculation_basis':'NOT_CALCULATED'},
        'execution_authority':False,'trading_authorized':False,'training_authorized':False,'production_runtime_admission':'BLOCKED'}
    _cancel(cancel_check)
    return {'descriptor':descriptor,'artifact_bytes':raw}
