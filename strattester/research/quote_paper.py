"""Declared-receipt quote paper research; no exchange/order/network authority.

Receipt hashes bind caller declarations, not authenticity. Funding completeness is
caller-admitted schedule evidence. SQLite is node-local durability, not consensus.
"""
from __future__ import annotations
import hashlib,json,math,os,re,sqlite3,stat
from contextlib import closing
from pathlib import Path
from .execution import _adverse
SYMBOLS=frozenset(x+'USDT' for x in ('BTC','ETH','SOL','XRP','BNB','DOGE','ADA','AVAX','LINK','DOT'))
# Deliberately bounded node-local research ledger, never an unbounded live store.
MAX_LEDGER_TRADES=1024
MAX_LEDGER_RECEIPTS=MAX_LEDGER_TRADES*134
MAX_CANONICAL_BYTES=262144
LABEL=re.compile(r'[A-Za-z0-9_-]{1,128}\Z');HEX=re.compile(r'[a-f0-9]{64}\Z')
def need(ok):
 if not ok:raise ValueError('INVALID_PAPER_RESEARCH')
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def fields(v,keys):need(type(v) is dict and set(v)==set(keys))
def clock(v):need(type(v) is int and 0<=v<=2**53-1);return v
def num(v,lo=0,hi=1e12):need(type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi);return v
def label(v):need(type(v) is str and LABEL.fullmatch(v) is not None)
def receipt(v,keys):
 fields(v,('receipt_id','source_id','raw_sha256','sha256','symbol',*keys))
 label(v['receipt_id']);label(v['source_id'])
 need(type(v['raw_sha256']) is str and HEX.fullmatch(v['raw_sha256']) is not None)
 need(type(v['sha256']) is str and v['sha256']==digest({k:x for k,x in v.items() if k!='sha256'}))

def evaluate(p,*,now_ms):
 try:return _evaluate(p,now_ms)
 except (TypeError,KeyError,OverflowError,RecursionError) as e:raise ValueError('INVALID_PAPER_RESEARCH') from e

def _evaluate(p,now):
 clock(now);fields(p,('schema','request_id','strategy','strategy_revision','evidence_class','symbol','units','policy','signal','close_signal','quotes','funding'))
 need(p['schema']=='stratt.paper.quote.request.v1');label(p['request_id']);label(p['strategy']);need(type(p['symbol']) is str and p['symbol'] in SYMBOLS)
 need(type(p['strategy_revision']) is str and re.fullmatch('[a-f0-9]{40}',p['strategy_revision']) is not None)
 need(type(p['evidence_class']) is str and p['evidence_class'] in ('SYNTHETIC','HISTORICAL','LIVE'))
 need(p['units']==dict(price='USDT/'+p['symbol'][:-4],qty=p['symbol'][:-4]))
 policy=p['policy'];fields(policy,('notional','fee_bps','slippage_bps','latency_ms','max_quote_age_ms','max_hold_ms'))
 num(policy['notional'],1e-9);num(policy['fee_bps'],0,1000);num(policy['slippage_bps'],0,1000)
 for k in ('latency_ms','max_quote_age_ms','max_hold_ms'):need(1<=clock(policy[k])<=3600000)
 a,b=p['signal'],p['close_signal'];receipt(a,('decision_ms','observed_ms','expires_ms','side'));receipt(b,('decision_ms','observed_ms','expires_ms'))
 need(a['side'] in ('long','short'))
 for s in (a,b):need(clock(s['observed_ms'])<=clock(s['decision_ms'])<clock(s['expires_ms'])<=now+3600000)
 quotes=p['quotes'];need(type(quotes) is list and len(quotes)==2)
 for q,s in zip(quotes,(a,b)):
  receipt(q,('epoch','sequence','event_ms','observed_ms','bid','ask'));label(q['epoch']);clock(q['sequence'])
  need(clock(q['event_ms'])<=clock(q['observed_ms'])<=now)
  need(q['observed_ms']-q['event_ms']<=policy['max_quote_age_ms'])
  need(s['decision_ms']+policy['latency_ms']<=min(q['event_ms'],q['observed_ms']))
  need(max(q['event_ms'],q['observed_ms'])<=s['expires_ms'])
  num(q['bid'],1e-12);num(q['ask'],1e-12);need(q['bid']<=q['ask'])
 x,y=quotes;need(x['epoch']==y['epoch'] and x['source_id']==y['source_id'] and x['sequence']<y['sequence'])
 need(x['event_ms']<y['event_ms'] and x['observed_ms']<y['observed_ms'] and x['observed_ms']<=b['decision_ms'])
 need(max(y['event_ms']-x['event_ms'],y['observed_ms']-x['observed_ms'])<=policy['max_hold_ms'] and now-y['event_ms']<=policy['max_quote_age_ms'])
 side=a['side'];rawentry=x['ask'] if side=='long' else x['bid'];rawexit=y['bid'] if side=='long' else y['ask']
 entry=_adverse(rawentry,side,policy['slippage_bps'],True);exit=_adverse(rawexit,side,policy['slippage_bps'],False)
 qty=policy['notional']/entry;signed=qty if side=='long' else -qty
 f=p['funding'];receipt(f,('kind','observed_ms','previous_ms','next_ms','interval_ms','events'))
 prev,nxt,interval=(clock(f[k]) for k in ('previous_ms','next_ms','interval_ms'));need(1<=interval<=86400000 and prev<=x['event_ms']<y['event_ms']<nxt and (nxt-prev)%interval==0)
 need(clock(f['observed_ms'])<=now)
 events=f['events'];need(type(events) is list and len(events)<=128)
 need((nxt-prev)//interval-1<=128);expected=list(range(prev+interval,nxt,interval))
 need(f['kind'] in ('COMPLETE_INTERVAL','COMPLETE_EVENTS'))
 need((f['kind']=='COMPLETE_INTERVAL' and nxt-prev==interval and not events and prev<=f['observed_ms']<nxt and f['observed_ms']<=x['observed_ms']) or (f['kind']=='COMPLETE_EVENTS' and bool(events)))
 need(len(events)==len(expected));funding=0.
 for e,t in zip(events,expected):
  receipt(e,('event_ms','observed_ms','rate','mark_price'));need(clock(e['event_ms'])==t<=clock(e['observed_ms'])<=f['observed_ms']<=now);num(e['rate'],-1,1);num(e['mark_price'],1e-12)
  if x['event_ms']<=t<y['event_ms']:funding+=signed*e['mark_price']*e['rate']
 receipts=[a,b,x,y,f,*events];need(all(r['symbol']==p['symbol'] for r in receipts));ids=[r['receipt_id'] for r in receipts];need(len(ids)==len(set(ids)))
 rawgross=signed*(rawexit-rawentry);gross=signed*(exit-entry);slip=rawgross-gross;fees=qty*(entry+exit)*policy['fee_bps']/10000;pnl=rawgross-slip-fees-funding
 for v in (qty,signed,rawgross,gross,slip,fees,funding,pnl):num(v,-1e15,1e15)
 need(len(canonical(p))<=262144)
 return dict(schema='stratt.paper.quote.result.v1',mode='PUBLIC_QUOTE_PAPER_RESEARCH',trade_id=p['request_id'],strategy=p['strategy'],strategy_revision=p['strategy_revision'],evidence_class=p['evidence_class'],request_sha256=digest(p),symbol=p['symbol'],units=dict(p['units']),side='BUY' if side=='long' else 'SELL',status='CLOSED',entry_ts_ms=x['event_ms'],exit_ts_ms=y['event_ms'],entry_price=entry,exit_price=exit,raw_entry_price=rawentry,raw_exit_price=rawexit,qty=qty,signed_qty=signed,gross_raw=rawgross,gross_fill=gross,fees=fees,slippage=slip,funding=funding,pnl=pnl,receipt_bindings=[dict(receipt_id=r['receipt_id'],sha256=r['sha256']) for r in receipts],source_authenticity='NOT_EVALUATED',receipt_provenance='CALLER_DECLARED',fill_selection='CALLER_SUPPLIED_CAUSAL_QUOTES_NOT_COMPLETE_MARKET_STREAM',missing_capabilities=['MARKET_DEPTH_LIQUIDITY','ACTUAL_EXCHANGE_FILLS','STREAM_COMPLETENESS_ATTESTATION'],execution_authority=False,trading_authorized=False,training_authorized=False,grid_normal='NOT_QUALIFIED',paper_eligible='NOT_QUALIFIED',h_b='NOT_QUALIFIED',durability='NODE_LOCAL_NOT_DISTRIBUTED_CONSENSUS_OR_FAILOVER')

class PaperLedger:
 """Node-local receipts under an externally admitted private parent directory.

 Not an ownership attestation or final distributed ledger. Repeated requests
 revalidate their stored result at its original admission clock, not today's
 quote-freshness clock. Corruption never becomes a successful duplicate reply.
 """
 APPLICATION_ID=0x5551504c
 def __init__(self,path):
  self.path=Path(path);self._identity=None;self._regular()
  try:
   with self.path.open('rb') as f:header=f.read(100)
   need(len(header)==100 and header[:16]==b'SQLite format 3\0' and int.from_bytes(header[68:72],'big')==self.APPLICATION_ID and int.from_bytes(header[60:64],'big')==2)
   with closing(sqlite3.connect(self.path)) as c,c:
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    need(tables=={'receipts','trades'})
    need({r[1] for r in c.execute('PRAGMA table_info(receipts)')}=={'receipt_id','sha256'})
    need({r[1] for r in c.execute('PRAGMA table_info(trades)')}=={'request_id','signal_id','request_sha256','admitted_ms','result_sha256','result','request'})
  except (OSError,sqlite3.DatabaseError) as exc:raise ValueError('INVALID_PAPER_LEDGER') from exc
  s=self.path.stat();self._identity=(s.st_dev,s.st_ino)
 def _regular(self):
  need(self.path.is_absolute())
  for p in (self.path,*self.path.parents):
   s=p.lstat();need(not stat.S_ISLNK(s.st_mode) and not getattr(s,'st_file_attributes',0)&0x400)
  s=self.path.stat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1)
  if self._identity is not None:need((s.st_dev,s.st_ino)==self._identity)
  for suffix in ('-journal','-wal','-shm'):
   side=Path(str(self.path)+suffix)
   if side.exists() or side.is_symlink():
    info=side.lstat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400)
 @classmethod
 def create(cls,path):
  path=Path(path)
  need(path.is_absolute())
  # Refuse linked/reparse ancestors before exclusive creation.
  for p in (path.parent,*path.parent.parents):
   s=p.lstat();need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode) and not getattr(s,'st_file_attributes',0)&0x400)
  fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
  with closing(sqlite3.connect(path)) as c,c:
   c.execute('PRAGMA synchronous=FULL')
   c.execute('PRAGMA application_id='+str(cls.APPLICATION_ID));c.execute('PRAGMA user_version=2')
   c.execute('CREATE TABLE receipts(receipt_id TEXT PRIMARY KEY,sha256 TEXT NOT NULL)')
   c.execute('CREATE TABLE trades(request_id TEXT PRIMARY KEY,signal_id TEXT UNIQUE NOT NULL,request_sha256 TEXT NOT NULL,admitted_ms INTEGER NOT NULL,result_sha256 TEXT NOT NULL,result TEXT NOT NULL,request TEXT NOT NULL)')
  return cls(path)
 def _validate_existing(self,c,request_id):
  """Recompute every bounded v2 row before trusting any uniqueness index.

  Canonical requests are retained so repaired result checksums cannot conceal
  arithmetic/index corruption. Format v1 is rejected, never auto-migrated.
  Hashes detect inconsistent declarations, not hostile-writer authenticity.
  """
  need(c.execute('PRAGMA application_id').fetchone()[0]==self.APPLICATION_ID and c.execute('PRAGMA user_version').fetchone()[0]==2)
  count=c.execute('SELECT COUNT(*) FROM trades').fetchone()[0];need(count<=MAX_LEDGER_TRADES)
  receipt_count=c.execute('SELECT COUNT(*) FROM receipts').fetchone()[0];need(receipt_count<=MAX_LEDGER_RECEIPTS)
  # Reject oversize/type-invalid columns inside SQLite before loading any rows.
  bad=c.execute("""SELECT COUNT(*) FROM trades WHERE
   typeof(request_id)!='text' OR length(CAST(request_id AS BLOB))>128 OR
   typeof(signal_id)!='text' OR length(CAST(signal_id AS BLOB))>128 OR
   typeof(request_sha256)!='text' OR length(CAST(request_sha256 AS BLOB))!=64 OR
   typeof(result_sha256)!='text' OR length(CAST(result_sha256 AS BLOB))!=64 OR
   typeof(admitted_ms)!='integer' OR admitted_ms<0 OR admitted_ms>9007199254740991 OR
   typeof(request)!='text' OR length(CAST(request AS BLOB)) NOT BETWEEN 1 AND ? OR
   typeof(result)!='text' OR length(CAST(result AS BLOB)) NOT BETWEEN 1 AND ?""",(MAX_CANONICAL_BYTES,MAX_CANONICAL_BYTES)).fetchone()[0]
  need(bad==0)
  bad=c.execute("""SELECT COUNT(*) FROM receipts WHERE
   typeof(receipt_id)!='text' OR length(CAST(receipt_id AS BLOB)) NOT BETWEEN 1 AND 128 OR
   typeof(sha256)!='text' OR length(CAST(sha256 AS BLOB))!=64""").fetchone()[0]
  need(bad==0)
  expected_receipts={};requests=set();signals=set();prior=None
  for rid,sid,request_hash,admitted,result_hash,result_text,request_text in c.execute('SELECT request_id,signal_id,request_sha256,admitted_ms,result_sha256,result,request FROM trades'):
   label(rid);label(sid);clock(admitted)
   need(rid not in requests and sid not in signals);requests.add(rid);signals.add(sid)
   need(type(request_hash) is str and HEX.fullmatch(request_hash) is not None and type(result_hash) is str and HEX.fullmatch(result_hash) is not None)
   need(type(request_text) is str and type(result_text) is str)
   original=json.loads(request_text);stored=json.loads(result_text)
   need(canonical(original)==request_text.encode('utf8') and canonical(stored)==result_text.encode('utf8'))
   need(digest(original)==request_hash and digest(stored)==result_hash)
   computed=evaluate(original,now_ms=admitted)
   need(original['request_id']==rid and original['signal']['receipt_id']==sid)
   need(canonical(computed)==canonical(stored))
   for binding in computed['receipt_bindings']:
    old=expected_receipts.get(binding['receipt_id'])
    need(old is None or old==binding['sha256']);expected_receipts[binding['receipt_id']]=binding['sha256']
   if rid==request_id:prior=(request_hash,stored)
  actual_receipts={}
  for rid,sha in c.execute('SELECT receipt_id,sha256 FROM receipts'):
   label(rid);need(type(sha) is str and HEX.fullmatch(sha) is not None and rid not in actual_receipts);actual_receipts[rid]=sha
  need(actual_receipts==expected_receipts)
  return prior,count
 def append(self,p,*,now_ms):
  self._regular();raw=canonical(p);need(len(raw)<=MAX_CANONICAL_BYTES);request=hashlib.sha256(raw).hexdigest();label(p['request_id'])
  with closing(sqlite3.connect(self.path)) as c,c:
   c.execute('PRAGMA synchronous=FULL');c.execute('BEGIN IMMEDIATE')
   prior,count=self._validate_existing(c,p['request_id'])
   if prior:
    need(prior[0]==request)
    return prior[1]
   need(count<MAX_LEDGER_TRADES)
   result=evaluate(p,now_ms=now_ms)
   need(c.execute('SELECT 1 FROM trades WHERE signal_id=?',(p['signal']['receipt_id'],)).fetchone() is None)
   for r in result['receipt_bindings']:
    old=c.execute('SELECT sha256 FROM receipts WHERE receipt_id=?',(r['receipt_id'],)).fetchone()
    if old:need(old[0]==r['sha256'])
    else:c.execute('INSERT INTO receipts VALUES(?,?)',(r['receipt_id'],r['sha256']))
   c.execute('INSERT INTO trades VALUES(?,?,?,?,?,?,?)',(p['request_id'],p['signal']['receipt_id'],request,now_ms,digest(result),canonical(result).decode(),raw.decode()))
  return result
