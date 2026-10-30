"""Independent readonly post-run oracle. Never imports collector implementation."""
import sqlite3,json,hashlib,re
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
HEAD='11b6c793e6617c3de08e6ca4fa741625c54c1951'
SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT');STEPS={'1m':60000,'5m':300000}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def strict_json(data):
 def pairs(items):
  out={}
  for k,v in items:
   if k in out:raise ValueError('DUPLICATE_JSON')
   out[k]=v
  return out
 return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
def inspect_database(path,session,details=False):
 path=Path(path)
 if path.is_symlink() or any(Path(str(path)+s).exists() for s in ('-wal','-shm','-journal')):raise ValueError('UNCLEAN_OR_LINKED_DATABASE')
 db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1);db.execute('PRAGMA query_only=ON')
 try:
  if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('DB_INTEGRITY')
  identity=[strict_json(r[0]) for r in db.execute('select payload from identity')]
  if identity!=[session]:raise ValueError('DATABASE_IDENTITY')
  sources={};captures=[]
  for id,body,rawmeta in db.execute('select id,body,meta from sources'):
   meta=strict_json(rawmeta);payload=strict_json(body)
   if type(body) is not bytes or len(body)>2*1024*1024 or hashlib.sha256(body).hexdigest()!=meta.get('body_sha256') or len(body)!=meta.get('body_bytes') or meta.get('status')!=200 or meta.get('path') not in ('/v5/market/time','/v5/market/instruments-info','/v5/market/kline') or type(payload.get('retCode')) is not int or payload['retCode']!=0:raise ValueError('SOURCE_PROVENANCE')
   observed=meta.get('observed_end_utc')
   if type(observed) is not str or datetime.fromisoformat(observed).utcoffset()!=timezone.utc.utcoffset(None):raise ValueError('OBSERVATION_TIME')
   started=meta.get('observed_start_utc')
   if type(started) is not str:raise ValueError('OBSERVATION_START')
   dt_start=datetime.fromisoformat(started);dt_end=datetime.fromisoformat(observed)
   if dt_start.utcoffset()!=timezone.utc.utcoffset(None) or dt_start>dt_end:raise ValueError('OBSERVATION_ORDER')
   captures.append((meta,payload))
   if meta['path']=='/v5/market/kline':
    params=meta['params'];r=payload.get('result',{});rows=r.get('list')
    if params.get('category')!='linear' or r.get('category')!='linear' or r.get('symbol')!=params.get('symbol') or type(rows) is not list or len(rows)>1000:raise ValueError('SOURCE_PAGE_IDENTITY')
    mapped={}
    for v in rows:
     if type(v) is not list or len(v)!=7 or not isinstance(v[0],str) or not v[0].isdigit() or int(v[0]) in mapped:raise ValueError('SOURCE_DUPLICATE_OR_ROW')
     mapped[int(v[0])]=v
    sources[id]=(params,mapped,observed)
  seen={(s,tf):set() for s in SYMBOLS for tf in STEPS}
  for symbol,tf,t,raw,id in db.execute('select symbol,tf,t,values_json,source_id from candles'):
   if symbol not in SYMBOLS or tf not in STEPS or id not in sources:raise ValueError('CANDLE_IDENTITY')
   step=STEPS[tf];params,mapped,observed=sources[id];values=strict_json(raw)
   if params.get('symbol')!=symbol or params.get('interval')!=('1' if tf=='1m' else '5') or mapped.get(t)!=values or t%step or not session['start']<=t<session['end'] or t+step>session['end'] or not params['start']<=t<=params['end'] or int(values[0])!=t:raise ValueError('CANDLE_BINDING_OR_GRID')
   ns=[Decimal(x) for x in values[1:]]
   if not all(x.is_finite() and abs(x)<=Decimal('1e100') for x in ns):raise ValueError('NONFINITE_CANDLE')
   o,h,l,c,vol,turn=ns
   if min(o,h,l,c)<=0 or not l<=o<=h or not l<=c<=h or min(vol,turn)<0 or t in seen[(symbol,tf)]:raise ValueError('CANDLE_QUALITY')
   if t+step>int(datetime.fromisoformat(observed).timestamp()*1000):raise ValueError('CLOSE_AFTER_OBSERVATION')
   seen[(symbol,tf)].add(t)
  coverage={}
  for s in SYMBOLS:
   coverage[s]={}
   for tf,step in STEPS.items():
    expected=(session['end']-session['start'])//step;times=seen[(s,tf)];missing=expected-len(times)
    coverage[s][tf]={'state':'READY' if missing==0 else 'PARTIAL' if times else 'MISSING','expected':expected,'count':len(times),'missing_count':missing,'first_missing':next((t for t in range(session['start'],session['end'],step) if t not in times),None)}
  return (coverage,captures) if details else coverage
 finally:db.close()
def verify_checkpoint(path,pin):
 path=Path(path)
 if not re.fullmatch('[a-f0-9]{64}',str(pin)) or path.stat().st_size>128*1024 or sha(path)!=pin:raise ValueError('CHECKPOINT_SHA')
 cp=strict_json(path.read_bytes());s=cp.get('session',{})
 if cp.get('schema')!='history-batch-v1' or cp.get('head')!=HEAD or cp.get('status') not in ('PARTIAL','READY') or s.get('head')!=HEAD or s.get('category')!='linear' or s.get('symbols')!=list(SYMBOLS) or not re.fullmatch('[a-f0-9]{32}',str(s.get('id',''))):raise ValueError('CHECKPOINT_IDENTITY')
 if type(s.get('start')) is not int or type(s.get('end')) is not int or s['start']<0 or s['end']-s['start']!=30*86400000 or s['start']%300000:raise ValueError('CHECKPOINT_WINDOW')
 if type(cp.get('batch_index')) is not int or not 1<=cp['batch_index']<=16 or type(cp.get('batch_requests')) is not int or not 1<=cp['batch_requests']<=20 or type(cp.get('session_requests')) is not int or not cp['batch_requests']<=cp['session_requests']<=256:raise ValueError('CHECKPOINT_BUDGET')
 db=path.parent/'history.sqlite3'
 if sha(db)!=cp.get('database_sha256'):raise ValueError('DATABASE_SHA')
 actual,captures=inspect_database(db,s,details=True)
 if actual!=cp.get('coverage') or sha(db)!=cp['database_sha256']:raise ValueError('COVERAGE_OR_CHANGED_SOURCE')
 _verify_accounting_and_eligibility(path,cp,captures)
 eligible=cp.get('eligible')
 if type(eligible) is not list or len(set(eligible))!=len(eligible) or any(x not in SYMBOLS for x in eligible):raise ValueError('ELIGIBLE_IDENTITY')
 ready=all(v['state']=='READY' and sym in eligible for sym,bytf in actual.items() for v in bytf.values())
 if (cp['status']=='READY')!=ready:raise ValueError('FALSE_READY')
 return {'status':'CHECKPOINT_CONSISTENT','history_state':cp['status'],'coverage':actual,'source_sha256':cp['database_sha256'],'historical_availability':'NOT_ESTABLISHED','real_oos':'NOT_AUTHORIZED'}
def _verify_accounting_and_eligibility(path,cp,captures):
 grouped={}
 for meta,payload in captures:
  n=meta.get('batch_index');q=meta.get('batch_request')
  if type(n) is not int or not 1<=n<=cp['batch_index'] or type(q) is not int or not 1<=q<=20:raise ValueError('SOURCE_REQUEST_SEQUENCE')
  bucket=grouped.setdefault(n,{})
  if q in bucket:raise ValueError('SOURCE_REQUEST_REPLAY')
  bucket[q]=(meta,payload)
 if set(grouped)!=set(range(1,cp['batch_index']+1)) or any(set(b)!=set(range(1,len(b)+1)) for b in grouped.values()) or len(captures)!=cp['session_requests'] or len(grouped[cp['batch_index']])!=cp['batch_requests']:raise ValueError('REQUEST_ACCOUNTING')
 root=path.parent.parent;child=cp
 for n in range(cp['batch_index']-1,0,-1):
  ancestor=root/f'batch-{n:04}'/'checkpoint.json';pin=child['parent_checkpoint_sha256']
  if sha(ancestor)!=pin:raise ValueError('PARENT_CHECKPOINT_SHA')
  parent=strict_json(ancestor.read_bytes())
  if parent.get('batch_index')!=n or parent.get('session')!=cp['session'] or parent.get('head')!=HEAD or parent.get('status') not in ('PARTIAL','READY') or parent.get('session_requests')!=sum(len(grouped[i]) for i in range(1,n+1)) or parent.get('batch_requests')!=len(grouped[n]) or sha(ancestor.parent/'history.sqlite3')!=parent.get('database_sha256'):raise ValueError('PARENT_IDENTITY_ACCOUNTING')
  child=parent
 if child.get('parent_checkpoint_sha256') is not None:raise ValueError('INITIAL_PARENT')
 rows=grouped[cp['batch_index']];first_meta,first_payload=rows[1]
 if first_meta['path']!='/v5/market/time' or first_meta['params']!={}:raise ValueError('TIME_REQUEST')
 server=int(first_payload['result']['timeNano'])//1000000
 if cp['session']['end']>((server-60000)//300000)*300000:raise ValueError('FUTURE_SESSION')
 cursor='';seen=set();eligible=[];pages=0;terminal=False
 for q in range(2,len(rows)+1):
  meta,payload=rows[q]
  if meta['path']!='/v5/market/instruments-info':break
  if terminal:raise ValueError('EXTRA_UNIVERSE_PAGE')
  params=meta['params'];result=payload.get('result',{});items=result.get('list')
  expected={'category':'linear','status':'Trading','limit':1000}
  if cursor:expected['cursor']=cursor
  if params!=expected or result.get('category')!='linear' or type(items) is not list or len(items)>1000:raise ValueError('UNIVERSE_REQUEST_IDENTITY')
  pages+=1
  for item in items:
   symbol=item.get('symbol')
   if type(symbol) is not str or symbol in seen or item.get('status')!='Trading':raise ValueError('UNIVERSE_REPLAY_IDENTITY')
   seen.add(symbol);launch=item.get('launchTime');delivery=item.get('deliveryTime');region=item.get('marketRegion');contract=item.get('contractType')
   if symbol in SYMBOLS and type(launch) is str and launch.isdigit() and 0<int(launch)<=cp['session']['start'] and contract=='LinearPerpetual' and not region and (not delivery or delivery=='0' or type(delivery) is str and delivery.isdigit() and int(delivery)>=cp['session']['end']):eligible.append(symbol)
  next_cursor=result.get('nextPageCursor','')
  if type(next_cursor) is not str or (next_cursor and (next_cursor==cursor or not items)):raise ValueError('CURSOR_IDENTITY')
  cursor=next_cursor;terminal=not cursor
 if not terminal or not 1<=pages<=4 or sorted(eligible)!=cp.get('eligible'):raise ValueError('INDEPENDENT_ELIGIBILITY')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--sha256',required=True);args=p.parse_args();print(json.dumps(verify_checkpoint(args.checkpoint,args.sha256),sort_keys=True))
