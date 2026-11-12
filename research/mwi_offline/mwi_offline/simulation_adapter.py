"""Validated adapter to an existing pure simulator; no fills engine or ledger."""
import hashlib
import math
import json
import os
import stat
import importlib.util
import subprocess
import sys
import sysconfig
import uuid
from pathlib import Path
from .adapter import _safe, _bars
from .strategy import propose

PINS={'strattester/__init__.py':'20c8e430ededc2143396e553a3c67aac4ec483ef54efdfcb18a31cb162ca0646',
      'strattester/research/__init__.py':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      'strattester/research/execution.py':'99c1a3a7907b0481c0f2a4f239fb6808f137834b39fffaf7885ef60f66246832'}


def _plain(value,depth=0):
    if depth>16:raise ValueError('PLAIN_DEPTH')
    if value is None or type(value) in (str,bool,int):
        if type(value) is str and len(value)>4096:raise ValueError('PLAIN_TEXT')
        if type(value) is int and not -2**53<value<2**53:raise ValueError('PLAIN_INTEGER_BOUNDS')
        return
    if type(value) is float:
        if not math.isfinite(value):raise ValueError('PLAIN_FINITE')
        return
    if type(value) is list and len(value)<=10000:
        for v in value:_plain(v,depth+1)
        return
    if type(value) is dict and len(value)<=64 and all(type(k) is str for k in value):
        for v in value.values():_plain(v,depth+1)
        return
    raise ValueError('BUILTIN_OWNED_DATA_REQUIRED')


def inspect_binding(repo_root):
    root=_safe(repo_root);raw={}
    for name,expected in PINS.items():
        path=_safe(root/name)
        with path.open('rb') as stream:
            st=os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>65536:raise ValueError('SOURCE_FILE_BOUNDS')
            data=stream.read(65537)
        if len(data)>65536 or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('SIMULATOR_RAW_SOURCE_PIN')
        raw[name]=hashlib.sha256(data).hexdigest()
    return {'repo_root':str(root),'required_raw_sha256':dict(PINS),'raw_sha256':raw,
            'execution_sha256':raw['strattester/research/execution.py'],
            'scope':'SOURCE_INSPECTION_ONLY_NOT_RUNTIME_ADMISSION'}


def materialize_binding(repo_root,destination):
    """Write a NEW owned capsule from exact Git blobs; never rewrite a checkout."""
    root=_safe(destination);sources={}
    for name,pin in PINS.items():
        argv=['git','--no-replace-objects','-c','core.hooksPath=NUL','-c','core.fsmonitor=false','-C',str(repo_root)]
        obj='HEAD:'+name # shallow hosted checkout also contains these exact pinned blobs
        size=int(subprocess.check_output(argv+['cat-file','-s',obj],timeout=5))
        if not 0<=size<=65536:raise ValueError('GIT_BLOB_BOUNDS')
        data=subprocess.check_output(argv+['show',obj],timeout=5)
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=pin:raise ValueError('GIT_RAW_BLOB_PIN')
        sources[name]=data
    root.mkdir()
    for name,data in sources.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    return inspect_binding(root)


def bind_existing(repo_root):
    """Developer synthetic binding after exact ROOT/A7-approved raw closure check."""
    if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:raise ValueError('ISOLATED_STDLIB_PROFILE_REQUIRED')
    import dataclasses
    info=inspect_binding(repo_root);root=Path(info['repo_root'])
    stdlib=Path(sysconfig.get_path('stdlib')).resolve()
    if not Path(dataclasses.__file__).resolve().is_relative_to(stdlib):raise ValueError('STDLIB_ORIGIN')
    namespace='_mwi_owned_'+uuid.uuid4().hex
    loaded=[]
    for suffix,name,package in (('', 'strattester/__init__.py',True),('.research','strattester/research/__init__.py',True),('.research.execution','strattester/research/execution.py',False)):
        module_name=namespace+suffix;path=root/name
        if module_name in sys.modules:raise ValueError('FRESH_NAMESPACE_REQUIRED')
        spec=importlib.util.spec_from_file_location(module_name,path,submodule_search_locations=[str(path.parent)] if package else None)
        module=importlib.util.module_from_spec(spec);sys.modules[module_name]=module;spec.loader.exec_module(module)
        if Path(module.__file__).resolve()!=path.resolve():raise ValueError('PACKAGE_ORIGIN')
        loaded.append(module)
    if inspect_binding(root)!=info:raise ValueError('SOURCE_CHANGED_DURING_IMPORT')
    m=loaded[-1]
    def call(signal,bars,policy,metadata=None):
        if inspect_binding(root)!=info:raise ValueError('SOURCE_CHANGED_BEFORE_CALL')
        if type(signal) is not m.Signal or type(policy) is not m.ExecutionPolicy:raise ValueError('OWNED_NATIVE_TYPES')
        _plain(vars(signal));_plain(vars(policy))
        _plain(bars);_plain(metadata)
        if type(bars) is not list or not 1<=len(bars)<=10000 or metadata is not None and type(metadata) is not dict:raise ValueError('PLAIN_INPUT_SHAPE')
        if type(signal.side) is not str or signal.side not in ('long','short') or type(signal.entry_kind) is not str or signal.entry_kind not in ('market','limit'):raise ValueError('NATIVE_SIGNAL')
        if type(signal.decision_time) is not int or not 0<=signal.decision_time<=2**53-1:raise ValueError('NATIVE_TIME')
        for v in (signal.stop_loss,signal.take_profit,policy.fee_rate,policy.slippage_bps,policy.position_usd):
            if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('NATIVE_NUMERIC')
        if min(signal.stop_loss,signal.take_profit)<=0 or (signal.stop_loss>=signal.take_profit if signal.side=='long' else signal.take_profit>=signal.stop_loss):raise ValueError('NATIVE_STOP_GEOMETRY')
        if type(policy.bar_ms) is not int or policy.bar_ms!=60000 or policy.ambiguous_policy!='SL_FIRST' or not 0<=policy.fee_rate<=.01 or not 0<=policy.slippage_bps<=100 or not 0<policy.position_usd<=100:raise ValueError('NATIVE_POLICY')
        if signal.entry_kind=='limit':
            price=signal.entry_price
            if type(price) not in (int,float) or not math.isfinite(price) or price<=0 or not min(signal.stop_loss,signal.take_profit)<price<max(signal.stop_loss,signal.take_profit):raise ValueError('LIMIT_PRICE')
        previous=-1
        for b in bars:
            if type(b) is not dict or set(b)!={'t','open','high','low','close'} or type(b['t']) is not int or not previous<b['t']<=2**53-1:raise ValueError('NATIVE_BAR_TIME')
            previous=b['t']
            for key in ('open','high','low','close'):
                if type(b[key]) not in (int,float) or not math.isfinite(b[key]) or b[key]<=0:raise ValueError('NATIVE_OHLC')
            if not b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:raise ValueError('NATIVE_OHLC')
        owned_bars=json.loads(json.dumps(bars,allow_nan=False));owned_meta=json.loads(json.dumps(metadata or {},allow_nan=False))
        try:return m.simulate_trade(signal,owned_bars,policy,metadata=owned_meta)
        except ValueError as exc:
            if str(exc)=='entry not filled':raise ValueError('ENTRY_NOT_FILLED') from None
            raise
        finally:
            if inspect_binding(root)!=info:raise ValueError('SOURCE_CHANGED_AFTER_CALL')
    return {'Signal':m.Signal,'ExecutionPolicy':m.ExecutionPolicy,'simulate_trade':call,
            'source_sha256':info['execution_sha256'],'scope':'PINNED_EXISTING_PURE_SIMULATOR_SYNTHETIC_DEVELOPER_ONLY'}


def simulate_candidate(strategy,example,p,bars,binding,capital=1000.,stress=False):
    for value in (strategy,example,p,bars):_plain(value)
    if type(capital) not in (int,float) or not math.isfinite(capital) or type(stress) is not bool:raise ValueError('CAPITAL_OR_SCENARIO')
    proposal=propose(strategy,example,p)
    if proposal['action']=='WAIT':return {'status':'WAIT','reason':proposal['reason']}
    rows=_bars(bars);symbol=example['id'].split(':')[0];cutoff=example['cutoff'];end=example['label_end']
    if type(cutoff) is not int or type(end) is not int or not 0<=cutoff<end<=cutoff+(strategy['horizon']+1)*60000 or end%60000:
        raise ValueError('BOUNDED_EXAMPLE_WINDOW')
    if symbol not in strategy['instruments']:return {'status':'REFUSED','reason':'INSTRUMENT_SCOPE'}
    touch=[b for b in rows if b['symbol']==symbol and b['end_ms']<=cutoff and b['available_ms']<=cutoff]
    if not touch:return {'status':'REFUSED','reason':'NO_AVAILABLE_REFERENCE'}
    touch=touch[-1];price=touch['close'];atr=example['baseline'][4]*price
    if capital<=0 or strategy['position_usd']>capital*.10 or atr<=0 or strategy['position_usd']*strategy['stop_atr']*atr/price>capital*strategy['max_risk_fraction']:
        return {'status':'REFUSED','reason':'EX_ANTE_VIRTUAL_RISK'}
    first=((cutoff+strategy['execution']['latency_ms']+59999)//60000)*60000
    required=list(range(first,end,60000))
    if not required:return {'status':'REFUSED','reason':'NO_FULL_POST_LATENCY_BAR'}
    index={b['open_ms']:b for b in rows if b['symbol']==symbol}
    if any(t not in index or index[t]['end_ms']!=t+60000 for t in required):return {'status':'REFUSED','reason':'DATA_GAP'}
    future=[{'t':t,**{k:index[t][k] for k in ('open','high','low','close')}} for t in required]
    direction=1 if proposal['side']=='long' else -1
    stop=price-direction*strategy['stop_atr']*atr;target=price+direction*strategy['target_atr']*atr
    if min(stop,target)<=0:return {'status':'REFUSED','reason':'STOP_GEOMETRY'}
    signal=binding['Signal'](decision_time=first,side=proposal['side'],entry_kind='market',entry_price=None,stop_loss=stop,take_profit=target)
    policy=binding['ExecutionPolicy'](bar_ms=60000,fee_rate=.001 if stress else strategy['execution']['fee_rate'],
                                    slippage_bps=8. if stress else strategy['execution']['slippage_bps'],
                                    ambiguous_policy='SL_FIRST',position_usd=strategy['position_usd'])
    # Native simulator owns all fill/exit/PnL decisions. Predictions never do.
    trade=binding['simulate_trade'](signal,future,policy,metadata={'strategy_id':strategy['strategy_id'],'example_id':example['id'],'scope':'SYNTHETIC_SCENARIO'})
    return {'status':'SIMULATED','trade':dict(vars(trade)),'strategy_id':strategy['strategy_id'],
            'simulator_sha256':binding['source_sha256'],'binding_scope':binding['scope'],
            'funding':'SYNTHETIC_ZERO_ASSUMPTION_NOT_OBSERVED','depth_partial_fills':'UNSUPPORTED',
            'cost_scenario':'STRESS' if stress else 'BASE','risk_scope':'EX_ANTE_STOP_ESTIMATE_NOT_GAP_LOSS_GUARANTEE'}
