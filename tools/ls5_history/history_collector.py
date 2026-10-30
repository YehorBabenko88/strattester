"""Bounded public-history batches. No network, strategies or training on import."""
import hashlib,json,os,sqlite3,uuid,re,shutil,time
from pathlib import Path
from decimal import Decimal
from public_core import strict,discover
HEAD='11b6c793e6617c3de08e6ca4fa741625c54c1951'
SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT');STEPS={'1m':60000,'5m':300000}
class BudgetReached(Exception):pass

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk)
 return h.hexdigest()
def unlinked(path):
 p=Path(path)
 for n in (p,*p.parents):
  if n.exists() and (n.is_symlink() or getattr(n.lstat(),'st_file_attributes',0)&0x400):raise ValueError('LINKED_PATH')
 return p.resolve()
def publish(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.partial')
 with tmp.open('xb') as f:f.write(canonical(value));f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def decode_file(path,pin):
 path=unlinked(path)
 if path.stat().st_size>128*1024 or sha(path)!=pin:raise ValueError('CHECKPOINT_HASH_OR_BOUND')
 def pairs(items):
  out={}
  for k,v in items:
   if k in out:raise ValueError('DUPLICATE_CHECKPOINT')
   out[k]=v
  return out
 return json.loads(path.read_bytes(),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('NONFINITE')))
class Lease:
 """Owned-directory OS file lock, not sandbox isolation or malicious-host rollback proof."""
 def __init__(self,root):self.path=Path(root)/'session.lock';self.file=None
 def __enter__(self):
  unlinked(self.path)
  if self.path.exists() and (self.path.stat().st_nlink!=1 or self.path.stat().st_size>1):raise ValueError('LEASE_FILE_IDENTITY')
  self.file=self.path.open('a+b')
  try:
   if self.file.seek(0,2)==0:self.file.write(b'0');self.file.flush();os.fsync(self.file.fileno())
   self.file.seek(0)
   if os.name=='nt':
    import msvcrt;msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl;fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
   return self
  except BaseException:self.file.close();raise
 def __exit__(self,*args):self.file.close()
def validate_row(v,step,a,b):
 if type(v) is not list or len(v)!=7 or any(type(x) is not str or len(x)>80 for x in v) or not v[0].isdigit():raise ValueError('ROW_SCHEMA')
 t=int(v[0]);ns=[Decimal(x) for x in v[1:]]
 if not all(n.is_finite() and abs(n)<=Decimal('1e100') for n in ns):raise ValueError('ROW_NONFINITE')
 o,h,l,c,vol,turn=ns
 if t%step or not a<=t<b or t+step>b or min(o,h,l,c)<=0 or not l<=o<=h or not l<=c<=h or min(vol,turn)<0:raise ValueError('ROW_GRID_QUALITY')
 return t

def run_batch(root,batch_name,fetch,*,previous=None,previous_sha=None,cancel=lambda:False,clock_utc_ms=lambda:int(time.time()*1000),cooldown=time.sleep):
 root=unlinked(root)
 if not root.is_dir() or not re.fullmatch('batch-[0-9]{4}',batch_name):raise ValueError('BATCH_ROOT')
 with Lease(root):return _run(root,batch_name,fetch,previous,previous_sha,cancel,clock_utc_ms,cooldown)

def _run(root,batch_name,fetch,previous,previous_sha,cancel,clock,cooldown):
 batch=root/batch_name
 if batch.exists():raise ValueError('ATTEMPT_EXISTS')
 state_path=root/'session-state.json';unlinked(state_path);prior=None
 if previous:
  cp=unlinked(previous)
  if cp.parent.parent!=root or cp.name!='checkpoint.json':raise ValueError('PREDECESSOR_SCOPE')
  prior=decode_file(cp,previous_sha)
  if prior.get('schema')!='history-batch-v1' or prior.get('status') not in ('PARTIAL','READY') or prior.get('head')!=HEAD:raise ValueError('PREDECESSOR_IDENTITY')
  state=json.loads(state_path.read_bytes())
  if state!={'checkpoint_sha256':previous_sha,'checkpoint':cp.parent.name+'/checkpoint.json','state':'COMMITTED'}:raise ValueError('STALE_OR_BLOCKED_PREDECESSOR')
  if int(batch_name[-4:])!=prior['batch_index']+1:raise ValueError('BATCH_SEQUENCE')
  dbsrc=unlinked(cp.parent/'history.sqlite3')
  if any(Path(str(dbsrc)+x).exists() for x in ('-journal','-wal','-shm')) or sha(dbsrc)!=prior['database_sha256']:raise ValueError('PREDECESSOR_DATABASE')
  # Independent full verifier before copying or admitting any request.
  from history_verify import verify_checkpoint
  verify_checkpoint(cp,previous_sha)
 else:
  if previous_sha or state_path.exists() or int(batch_name[-4:])!=1:raise ValueError('INITIAL_SESSION_IDENTITY')
 if prior and (prior['batch_index']>=16 or prior['session_requests']>=256):raise ValueError('SESSION_BUDGET')
 batch.mkdir();dbpath=batch/'history.sqlite3';db=None;used=0;session=None;eligible=[]
 publish(state_path,{'state':'IN_PROGRESS','batch':batch_name})
 try:
  if prior:
   # Copy through one retained input descriptor; reject changed content before publication.
   with dbsrc.open('rb') as f,dbpath.open('xb') as dst:shutil.copyfileobj(f,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
   if sha(dbpath)!=prior['database_sha256'] or sha(dbsrc)!=prior['database_sha256']:raise ValueError('PREDECESSOR_CHANGED')
   session=prior['session'];wait_start=time.monotonic_ns()
   while time.monotonic_ns()-wait_start<1_050_000_000:
    if cancel():raise InterruptedError('CANCELLED_RESTART_COOLDOWN')
    cooldown(.025) # every new batch starts after previous completed attempt
  db=sqlite3.connect(dbpath,timeout=1);db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA foreign_keys=ON')
  db.execute('CREATE TABLE IF NOT EXISTS identity(payload TEXT NOT NULL)')
  db.execute('CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,body BLOB NOT NULL,meta TEXT NOT NULL)')
  db.execute('CREATE TABLE IF NOT EXISTS candles(symbol TEXT,tf TEXT,t INTEGER,values_json TEXT NOT NULL,source_id INTEGER NOT NULL REFERENCES sources(id),PRIMARY KEY(symbol,tf,t))');db.commit()
  def call(path,params):
   nonlocal used
   if cancel():raise InterruptedError('CANCELLED')
   if used>=20 or (prior['session_requests'] if prior else 0)+used>=256:raise BudgetReached()
   used+=1
   body,meta=fetch(path,params)
   if cancel():raise InterruptedError('CANCELLED_AFTER_FETCH')
   if type(body) is not bytes or len(body)>2*1024*1024 or type(meta) is not dict or meta.get('path')!=path or meta.get('params')!=params or meta.get('status')!=200 or meta.get('body_sha256')!=hashlib.sha256(body).hexdigest() or meta.get('body_bytes')!=len(body) or not meta.get('observed_end_utc'):raise ValueError('CAPTURE_IDENTITY')
   payload=strict(body)
   db.execute('INSERT INTO sources(body,meta) VALUES(?,?)',(body,canonical(dict(meta,batch_index=int(batch_name[-4:]),batch_request=used)).decode()))
   call.source_id=db.execute('SELECT last_insert_rowid()').fetchone()[0];call.observed=meta['observed_end_utc'];return payload
  with db:now=call('/v5/market/time',{})
  server=int(now['result']['timeNano'])//1000000
  if abs(server-clock())>120000:raise ValueError('SERVER_CLOCK_SKEW')
  if not session:
   end=((server-60000)//300000)*300000
   if end<30*86400000:raise ValueError('SERVER_TIME')
   session={'id':uuid.uuid4().hex,'category':'linear','symbols':list(SYMBOLS),'start':end-30*86400000,'end':end,'head':HEAD}
   with db:db.execute('INSERT INTO identity VALUES(?)',(canonical(session).decode(),))
  elif [r[0] for r in db.execute('select payload from identity')]!=[canonical(session).decode()] or session['end']>((server-60000)//300000)*300000:raise ValueError('SESSION_REPLACEMENT')
  with db:universe=discover(call)
  for row in universe:
   symbol,launch,contract,settle,delivery,region=row['fields']
   if symbol in SYMBOLS and contract=='LinearPerpetual' and launch and launch.isdigit() and 0<int(launch)<=session['start'] and not region and (not delivery or delivery=='0' or delivery.isdigit() and int(delivery)>=session['end']):eligible.append(symbol)
  try:
   for symbol in SYMBOLS:
    if symbol not in eligible:continue
    for tf,step in STEPS.items():
     while True:
      if cancel():raise InterruptedError('CANCELLED')
      present={r[0] for r in db.execute('select t from candles where symbol=? and tf=?',(symbol,tf))}
      a=next((t for t in range(session['start'],session['end'],step) if t not in present),None)
      if a is None:break
      b=a+step
      while b<session['end'] and b not in present and (b-a)//step<1000:b+=step
      with db:
       data=call('/v5/market/kline',dict(category='linear',symbol=symbol,interval='1' if tf=='1m' else '5',start=a,end=b-1,limit=1000));result=data.get('result',{})
       if result.get('category')!='linear' or result.get('symbol')!=symbol or type(result.get('list')) is not list or len(result['list'])>1000:raise ValueError('PAGE_IDENTITY')
       last=None
       for row in result['list']:
        t=validate_row(row,step,a,b)
        if last is not None and t>=last:raise ValueError('PAGE_ORDER_DUPLICATE')
        last=t;db.execute('INSERT INTO candles VALUES(?,?,?,?,?)',(symbol,tf,t,canonical(row).decode(),call.source_id))
      if not result['list']:break # do not retry empty response in same batch
  except BudgetReached:pass
  if cancel():raise InterruptedError('CANCELLED_BEFORE_PUBLICATION')
  db.close();db=None
  from history_verify import inspect_database
  coverage=inspect_database(dbpath,session);ready=all(v['state']=='READY' and s in eligible for s,bytf in coverage.items() for v in bytf.values())
  receipt={'schema':'history-batch-v1','head':HEAD,'batch_index':int(batch_name[-4:]),'session':session,'parent_checkpoint_sha256':previous_sha,'database_sha256':sha(dbpath),'batch_requests':used,'session_requests':(prior['session_requests'] if prior else 0)+used,'status':'READY' if ready else 'PARTIAL','eligible':sorted(eligible),'coverage':coverage,'historical_availability':'UNKNOWN_BEFORE_FIRST_OBSERVATION','historical_revisions':'NOT_ESTABLISHED','strategies':'NOT_EXECUTED'}
  if cancel():raise InterruptedError('CANCELLED_BEFORE_CHECKPOINT')
  publish(batch/'checkpoint.json',receipt);pin=sha(batch/'checkpoint.json')
  from history_verify import verify_checkpoint
  verify_checkpoint(batch/'checkpoint.json',pin)
  if cancel():raise InterruptedError('CANCELLED_BEFORE_COMMIT')
  publish(state_path,{'state':'COMMITTED','checkpoint':batch_name+'/checkpoint.json','checkpoint_sha256':pin})
  return receipt
 except BaseException as exc:
  if db is not None:db.close()
  publish(state_path,{'state':'BLOCKED','batch':batch_name,'error_type':type(exc).__name__ if type(exc).__name__ in ('ValueError','RuntimeError','InterruptedError','TimeoutError') else 'OperationError'})
  publish(batch/'failure.json',{'status':'BLOCKED','phase':'COLLECTOR','safe_error_type':type(exc).__name__ if type(exc).__name__ in ('ValueError','RuntimeError','InterruptedError','TimeoutError') else 'OperationError','batch_requests':used,'retry':'NOT_AUTHORIZED'})
  raise
