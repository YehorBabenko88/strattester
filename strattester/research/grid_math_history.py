"""Historical research only: pinned Math process and deterministic replay.

No broker, service controller, database connection or training launcher imports.
The expected dataset pin and Math/runtime pins must come from operator policy,
not from the untrusted dataset or a compute response.
"""
import hashlib
from bisect import bisect_left
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time

FILES=('python/history_timeseries.py','python/history_nonlinear.py','python/history_worker.py')

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def runtime_pin():return hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
def number(v):return type(v) in (int,float) and math.isfinite(v)


class MathClient:
    """Snapshot exact Git blobs, then launch Python -I -S with stdlib only.

    Git source is copied by immutable blob, so later checkout edits cannot alter
    computation. Python/stdlib and OS are trusted local runtime, not attested by
    a response. Executable hash is an operator pin, not host attestation.
    """
    def __init__(self,root,commit,tree,python_sha256,*,timeout=5.,output_limit=32768,timed=False):
        self.root=Path(root);self.commit=commit;self.tree=tree;self.python_sha256=python_sha256
        if not number(timeout) or not 0<timeout<=10 or type(output_limit) is not int or not 1<=output_limit<=262144:raise ValueError('LIMITS')
        self.timeout=timeout;self.output_limit=output_limit;self.temp=None;self.calls=0;self.timed=timed

    def git(self,*args):
        try:return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.DEVNULL,timeout=10)
        except (subprocess.SubprocessError,OSError) as exc:raise ValueError('MATH_UNAVAILABLE') from exc

    def __enter__(self):
        if runtime_pin()!=self.python_sha256:raise ValueError('RUNTIME_PIN')
        if self.git('rev-parse','HEAD').decode().strip()!=self.commit or self.git('rev-parse',self.commit+'^{tree}').decode().strip()!=self.tree:raise ValueError('MATH_PIN')
        if self.git('status','--porcelain','--untracked-files=all').strip():raise ValueError('DIRTY_MATH')
        files=FILES+(('python/history_contract.py','python/history_timed_worker.py') if self.timed else ())
        contents={f:self.git('show',self.commit+':'+f) for f in files}
        self.manifest={f:hashlib.sha256(b).hexdigest() for f,b in contents.items()}
        self.temp=tempfile.TemporaryDirectory(prefix='strattester-math-')
        self.started=time.monotonic()
        self.path=Path(self.temp.name)
        for f,b in contents.items():(self.path/Path(f).name).write_bytes(b)
        return self

    def __exit__(self,*args):
        if self.temp:self.temp.cleanup();self.temp=None

    def _execute(self,q,worker='history_worker.py',input_limit=262144):
        if not self.temp:raise ValueError('CLIENT_CLOSED')
        self.calls+=1
        if self.calls>2000 or time.monotonic()-self.started>120:raise ValueError('EXPERIMENT_RESOURCE_LIMIT')
        raw=canonical(q)
        if len(raw)>input_limit:raise ValueError('INPUT_LIMIT')
        for f,h in self.manifest.items():
            if hashlib.sha256((self.path/Path(f).name).read_bytes()).hexdigest()!=h:raise ValueError('WORKER_TAMPER')
        # Regular files permit active byte limits without unbounded pipe reads.
        with tempfile.TemporaryFile() as inp,tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
            inp.write(raw);inp.seek(0)
            try:
                p=subprocess.Popen([sys.executable,'-I','-S',str(self.path/worker)],
                    stdin=inp,stdout=out,stderr=err,cwd=self.path)
                start=time.monotonic()
                try:
                    while p.poll() is None:
                        if time.monotonic()-start>self.timeout or out.tell()>self.output_limit or err.tell()>self.output_limit:raise ValueError('MATH_RESOURCE_LIMIT')
                        time.sleep(.005)
                    if p.returncode or time.monotonic()-start>self.timeout or out.tell()>self.output_limit or err.tell()>self.output_limit:raise ValueError('MATH_FAILED')
                finally:
                    if p.poll() is None:p.kill()
                    p.wait(timeout=2)
                out.seek(0);r=json.loads(out.read(self.output_limit+1))
            except (OSError,subprocess.SubprocessError,json.JSONDecodeError) as exc:raise ValueError('MATH_UNAVAILABLE') from exc
        if not isinstance(r,dict):raise ValueError('MATH_RESULT')
        return r

    def predict(self,prices,dataset_fingerprint,train_count=None):
        q={'schema':'math.history.request.v1','prices':prices,'dataset_fingerprint':dataset_fingerprint,
           'train_count':len(prices) if train_count is None else train_count}
        r=self._execute(q)
        if (r.get('schema')!='math.history.result.v1' or r.get('request_digest')!=digest(q)
            or r.get('dataset_fingerprint')!=dataset_fingerprint or r.get('kernel')!='grid-frozen-analog-v1'
            or any(r.get(k) is not False for k in ('execution_authority','trading_authorized','training_authorized'))
            or not number(r.get('forecast')) or r['forecast']<=0 or not number(r.get('volatility')) or r['volatility']<0):raise ValueError('MATH_RESULT')
        return r

    def predict_timed(self,rows,dataset,decision_ms,train_count,train_end_ms,model_version):
        if not self.timed:raise ValueError('TIMED_MATH_REQUIRED')
        q={'schema':'math.history.request.v1.1','rows':rows,'dataset_id':dataset['dataset_id'],
           'dataset_fingerprint':dataset['dataset_fingerprint'],'source':dataset['source'],
           'market':{k:dataset['request'][k] for k in ('venue','market_type','symbol')},
           'units':dataset['request']['units'],'decision_ms':decision_ms,'train_count':train_count,
           'train_end_ms':train_end_ms,'max_age_ms':dataset['request']['max_age_ms'],'model_version':model_version}
        r=self._execute(q,'history_timed_worker.py',2*1024*1024)
        expected={'schema':'math.history.result.v1.1','request_digest':digest(q),'dataset_id':q['dataset_id'],
            'dataset_fingerprint':q['dataset_fingerprint'],'prefix_digest':digest(rows),'source':q['source'],
            'model_version':model_version,'kernel':'grid-frozen-analog-v1','decision_ms':decision_ms,
            'train_end_ms':train_end_ms,'train_count':train_count,
            'feature_available_at_ms':max(x['available_at_ms'] for x in rows),
            'feature_event_end_ms':rows[-1]['event_end_ms'],'sample_count':len(rows),
            'forecast_target_event_end_ms':rows[-1]['event_end_ms']+60000,
            'watermark_ms':max(x['watermark_ms'] for x in rows),'source_authenticity':'NOT_EVALUATED_BY_MATH'}
        if any(r.get(k)!=v for k,v in expected.items()):raise ValueError('TIMED_MATH_BINDING')
        if (any(r.get(k) is not False for k in ('execution_authority','trading_authorized','training_authorized'))
            or not number(r.get('forecast')) or r['forecast']<=0 or not number(r.get('volatility')) or r['volatility']<0):raise ValueError('MATH_RESULT')
        return r


def admit(dataset,expected_pin):
    try:
        d=json.loads(canonical(dataset));q=d['request'];rows=d['rows']
        if len(canonical(d))>8*1024*1024 or d['schema'] not in ('grid.history.v1','grid.history.v1.1'):raise ValueError('SCHEMA')
        if expected_pin!=d['dataset_fingerprint'] or digest({k:v for k,v in d.items() if k!='dataset_fingerprint'})!=expected_pin:raise ValueError('DATASET_PIN')
        if d['evidence_class'] not in ('SYNTHETIC','HISTORICAL') or any(d[k] is not False for k in ('execution_authority','trading_authorized')):raise ValueError('AUTHORITY')
        if q['schema']!='grid.history.request.v1' or q['venue']!='bybit' or q['market_type'] not in ('linear','spot'):raise ValueError('IDENTITY')
        # First simulator is deliberately BTC/USDT unit-specific, never generic inference.
        if q['symbol']!='BTCUSDT' or q['units']!={'price':'USDT/BTC','volume':'BTC'}:raise ValueError('UNITS')
        if not all(type(q[k]) is int and 0<=q[k]<=2**53-1 for k in ('start_ms','end_ms','as_of_ms','max_age_ms')):raise ValueError('TIME')
        n=(q['end_ms']-q['start_ms'])//60000
        if q['start_ms']%60000 or q['end_ms']%60000 or not 60<=n<=2000 or len(rows)!=n:raise ValueError('COVERAGE')
        if not q['end_ms']<=q['as_of_ms']<=q['end_ms']+q['max_age_ms']:raise ValueError('STALE')
        if len(d['source_receipts'])!=n or any(not isinstance(x,str) or len(x)!=64 for x in d['source_receipts']):raise ValueError('RECEIPTS')
        for i,r in enumerate(rows):
            lo=q['start_ms']+i*60000
            if r['event_start_ms']!=lo or r['event_end_ms']!=lo+60000 or type(r['available_at_ms']) is not int or not lo+60000<=r['available_at_ms']<=q['as_of_ms']:raise ValueError('CHRONOLOGY')
            if any(not number(r[k]) for k in ('open','high','low','close','volume')):raise ValueError('NONFINITE')
            if not 0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] or r['volume']<0:raise ValueError('OHLCV')
        if d['schema']=='grid.history.v1.1':
            from .history_admission import validate_timed_envelope
            validate_timed_envelope(d)
        return d
    except (KeyError,TypeError,OverflowError) as exc:raise ValueError('DATASET_UNAVAILABLE') from exc


def replay(dataset,expected_pin,client,policy):
    """One-bar nonoverlapping positions. Slippage is deducted, not in fills.

    Positive funding means long pays, short receives; quote cash = side*qty*
    settlement mark*rate. Position is held on [entry_ms,exit_ms).
    Selection is fixed on validation net PnL; flat baseline costs zero.
    """
    d=admit(dataset,expected_pin);rows=d['rows'];q=d['request'];policy_bytes=canonical(policy)
    if len(policy_bytes)>262144:raise ValueError('POLICY_LIMIT')
    p=json.loads(policy_bytes)
    try:
        bounds=[q['start_ms'],p['train_end_ms'],p['validation_end_ms'],p['test_end_ms']]
        if any(type(x) is not int or x%60000 for x in bounds) or not bounds[0]<bounds[1]<bounds[2]<bounds[3]==q['end_ms']:raise ValueError('SPLITS')
        if any(not number(p[k]) or p[k]<0 for k in ('fee_bps','slippage_bps','notional','starting_cash')) or p['notional']<=0 or p['starting_cash']<=0:raise ValueError('COSTS')
        if type(p['latency_ms']) is not int or not 0<=p['latency_ms']<=60000:raise ValueError('LATENCY')
        funding=p['funding']
        if not isinstance(funding,list) or len(funding)>2000:raise ValueError('FUNDING_LIMIT')
        if p['funding_policy']=='NOT_APPLICABLE_SPOT':
            if q['market_type']!='spot' or funding:raise ValueError('FUNDING_POLICY')
        elif p['funding_policy']=='EXPLICIT_PERPETUAL':
            if q['market_type']!='linear' or not funding:raise ValueError('FUNDING_MISSING')
            interval=p.get('funding_interval_ms',60000);anchor=p.get('funding_anchor_ms',0)
            if type(interval) is not int or interval<=0 or type(anchor) is not int:raise ValueError('FUNDING_SCHEDULE')
            if (q['end_ms']-q['start_ms']+interval-1)//interval>2000:raise ValueError('FUNDING_LIMIT')
            expected=list(range(q['start_ms']+((anchor-q['start_ms'])%interval),q['end_ms'],interval))
            relevant=[f for f in funding if q['start_ms']<=f['timestamp_ms']<q['end_ms']]
            if [f['timestamp_ms'] for f in relevant]!=expected:raise ValueError('FUNDING_COVERAGE')
            if any(type(f['timestamp_ms']) is not int or not number(f['rate']) or not number(f['mark_price']) or f['mark_price']<=0 for f in funding):raise ValueError('FUNDING_NUMERIC')
        else:raise ValueError('FUNDING_POLICY')
    except (KeyError,TypeError) as exc:raise ValueError('POLICY_UNAVAILABLE') from exc
    # Never expose labels or complete dataset to prediction worker.
    train_count=0
    for row in rows:
        if row['event_end_ms']>bounds[1] or row['available_at_ms']>bounds[1]:break
        train_count+=1
    if train_count<20:raise ValueError('TRAIN_UNAVAILABLE')
    predictions=[];math_trace=[];timed=d['schema']=='grid.history.v1.1'
    if timed and p.get('model_version')!='grid-frozen-analog-v1':raise ValueError('MODEL_VERSION')
    entry_times=[row['event_start_ms'] for row in rows]
    for i in range(19,len(rows)-1):
        decision=rows[i]['available_at_ms']
        entry_index=bisect_left(entry_times,decision+p['latency_ms'],lo=i+1)
        if entry_index>=len(rows):continue
        prefix=rows[:i+1]
        if any(r['available_at_ms']>decision for r in prefix):continue
        if timed:
            r=client.predict_timed(prefix,d,decision,min(len(prefix),train_count),bounds[1],p['model_version'])
            math_trace.append({k:r[k] for k in ('request_digest','prefix_digest','decision_ms',
                'feature_available_at_ms','feature_event_end_ms','forecast_target_event_end_ms','sample_count',
                'watermark_ms','model_version','forecast','volatility','train_count')})
        else:r=client.predict([r['close'] for r in prefix],expected_pin,min(len(prefix),train_count))
        predictions.append((i,decision,r['forecast'],r['volatility'],entry_index))
    def trades(low,high,enabled=True,starting_cash=None):
        result=[];balance=p['starting_cash'] if starting_cash is None else starting_cash;previous_exit=0
        # Latest available signal wins if latency maps several decisions to one
        # executable bar. Positions are one-bar and cannot overlap.
        for i,decision,forecast,volatility,entry_index in sorted(predictions,key=lambda x:(x[4],-x[1],-x[0])):
            bar=rows[entry_index];entry_ms=bar['event_start_ms'];exit_ms=bar['event_end_ms']
            if entry_ms<low or exit_ms>high:continue # purge crossing labels
            if entry_ms<previous_exit:continue
            side=(1 if forecast>rows[i]['close'] else -1 if forecast<rows[i]['close'] else 0) if enabled else 0
            if q['market_type']=='spot' and side<0:side=0
            if not side:continue
            # Conservative full-notional collateral, with no implicit leverage,
            # borrowing, inventory creation or reinvestment of unrealized PnL.
            if balance<p['notional']*(1+(p['fee_bps']+p['slippage_bps'])/10000):continue
            qty=p['notional']/bar['open'];gross=side*qty*(bar['close']-bar['open'])
            turn=p['notional']+qty*bar['close'];fees=turn*p['fee_bps']/10000;slip=turn*p['slippage_bps']/10000
            cashfund=sum(side*qty*f['mark_price']*f['rate'] for f in funding if entry_ms<=f['timestamp_ms']<exit_ms)
            balance+=gross-fees-slip-cashfund
            previous_exit=exit_ms
            result.append({'decision_ms':decision,'entry_ms':entry_ms,'exit_ms':exit_ms,'entry_price':bar['open'],
              'exit_price':bar['close'],'side':side,'quantity':qty,'forecast':forecast,'gross_pnl':gross,
              'fees':fees,'slippage':slip,'funding':cashfund,'net_pnl':gross-fees-slip-cashfund})
        return result
    train_trades=trades(bounds[0],bounds[1])
    validation_cash=p['starting_cash']+sum(t['net_pnl'] for t in train_trades)
    validation=trades(bounds[1],bounds[2],starting_cash=validation_cash)
    selected='ANALOG' if sum(t['net_pnl'] for t in validation)>0 else 'FLAT'
    splits={};fills=[];equity=[];cash=p['starting_cash']
    for j,name in enumerate(('train','validation','test')):
        ts=trades(bounds[j],bounds[j+1],name!='test' or selected=='ANALOG',cash)
        metrics={k:sum(t[k] for t in ts) for k in ('gross_pnl','fees','slippage','funding','net_pnl')}
        splits[name]={'start_ms':bounds[j],'end_ms':bounds[j+1],'metrics':metrics,'trades':len(ts)}
        for t in ts:
            cash+=t['net_pnl'];fills.append({**t,'split':name});equity.append({'timestamp_ms':t['exit_ms'],'cash_usdt':cash})
    metrics={k:sum(t[k] for t in fills) for k in ('gross_pnl','fees','slippage','funding','net_pnl')}
    if not all(number(v) for v in (*metrics.values(),cash)):raise ValueError('NONFINITE_RESULT')
    candidates=[{'origin_ms':decision,'label_available_at_ms':rows[i+1]['available_at_ms'],
        'features':{'forecast':forecast,'volatility':volatility},'label_close':rows[i+1]['close'],
        'split':'test','eligible_for_training':False,
        **({'feature_event_end_ms':rows[i]['event_end_ms'],'label_event_end_ms':rows[i+1]['event_end_ms'],
            'label_revision':rows[i+1]['revision']} if timed else {})}
        for i,decision,forecast,volatility,entry_index in predictions
        if bounds[2]<=rows[i+1]['event_start_ms'] and rows[i+1]['event_end_ms']<=bounds[3]
           and (not timed or decision<rows[i+1]['event_end_ms'])]
    result={'schema':'strattester.terminan.result.v1','mode':'HISTORICAL_RESEARCH','evidence_class':d['evidence_class'],
      'dataset_fingerprint':expected_pin,'source':d['source'],'source_receipts':d['source_receipts'],
      'math':{'commit':client.commit,'tree':client.tree,'manifest':client.manifest,'python_sha256':client.python_sha256},
      'strategy':'one-bar-frozen-analog-direction-v1','selected_model':selected,
      'evaluation_protocol':'FROZEN_TRAIN_NEIGHBORS_VALIDATION_SELECTION_CAUSAL_QUERY',
      'train_count':train_count,'splits':splits,'metrics':metrics,'fills':fills,
      'equity':equity,'training_candidates':candidates,'policy':p,'units':{'cash':'USDT','price':'USDT/BTC','quantity':'BTC','time':'UTC_MS'},
      'training_candidate':'BLOCKED_SYNTHETIC' if d['evidence_class']=='SYNTHETIC' else 'REQUIRES_INDEPENDENT_OOS_REVIEW',
      'training_authorized':False,'execution_authority':False,'trading_authorized':False,
      'warnings':['SOURCE_PINS_REQUIRE_INDEPENDENT_PROVISIONING','LOCAL_RUNTIME_TRUSTED_NOT_ATTESTED',
                  'TRAIN_VALIDATION_CURVES_ARE_DIAGNOSTIC','NO_PROFITABILITY_OR_FORWARD_ERROR_CERTIFICATE']}
    if timed:
        result.update(schema='strattester.terminan.result.v1.1',dataset_id=d['dataset_id'],
            watermark_ms=d['watermark_ms'],market={k:q[k] for k in ('venue','market_type','symbol')},
            math_trace=math_trace,observations=d['rows'],source_request=q,
            model_version=p['model_version'],source_authenticity='REQUIRES_INDEPENDENT_RECEIPT_PROVISIONING')
    result['completion_receipt']=digest(result)
    return result
