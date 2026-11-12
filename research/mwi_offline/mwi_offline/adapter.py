"""Local synthetic-only normalized snapshot; not a shared/native admission contract."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

MAX_BYTES=10*1024*1024
MAX_ROWS=10000
SCHEMA='mwi.offline.normalized.synthetic.v1'
BAR_KEYS={'symbol','open_ms','end_ms','available_ms','open','high','low','close','volume'}
MANIFEST_KEYS={'schema','source_head','evidence_class','file','sha256','bytes','row_count','clock_unit','provenance','coverage','dataset_id','missingness'}

def _digest(data):return hashlib.sha256(data).hexdigest()
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def _hex(value,n):
 if type(value) is not str or re.fullmatch('[0-9a-f]{'+str(n)+'}',value) is None:raise ValueError('invalid external pin/source head')
def _safe(path):
 path=Path(os.path.abspath(path))
 for part in (path,*path.parents):
  try:s=part.lstat()
  except FileNotFoundError:continue
  if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):raise ValueError('linked/reparse path refused')
 return path

def _read(path):
 path=_safe(path)
 if not path.is_file():raise ValueError('regular file required')
 with path.open('rb') as stream:
  s=os.fstat(stream.fileno())
  if not stat.S_ISREG(s.st_mode) or s.st_size>MAX_BYTES or s.st_nlink!=1:raise ValueError('file bounds/link violation')
  data=stream.read(MAX_BYTES+1)
 if len(data)>MAX_BYTES:raise ValueError('input byte budget')
 return data

def _json(data):
 depth=0;quoted=False;escaped=False
 for byte in data:
  if quoted:
   if escaped:escaped=False
   elif byte==92:escaped=True
   elif byte==34:quoted=False
  elif byte==34:quoted=True
  elif byte in (91,123):
   depth+=1
   if depth>64:raise ValueError('JSON nesting budget')
  elif byte in (93,125):depth-=1
 def pairs(items):
  out={}
  for key,value in items:
   if key in out:raise ValueError('duplicate JSON key')
   out[key]=value
  return out
 def invalid(value):raise ValueError('nonfinite JSON')
 try:return json.loads(data,object_pairs_hook=pairs,parse_constant=invalid)
 except (UnicodeError,RecursionError,json.JSONDecodeError) as exc:raise ValueError('invalid JSON') from exc

def _bars(rows):
 if type(rows) is not list or not 1<=len(rows)<=MAX_ROWS:raise ValueError('bar count budget')
 previous={};last_key=None
 for row in rows:
  if type(row) is not dict or set(row)!=BAR_KEYS:raise ValueError('bar schema')
  symbol=row['symbol']
  if type(symbol) is not str or re.fullmatch('[A-Za-z0-9_.-]{1,64}',symbol) is None:raise ValueError('symbol')
  for key in ('open_ms','end_ms','available_ms'):
   if type(row[key]) is not int or not 0<=row[key]<=2**53-1:raise ValueError('clock integer/range')
  if not row['open_ms']<row['end_ms']<=row['available_ms']:raise ValueError('causal clock')
  key=(symbol,row['open_ms'])
  if last_key is not None and key<=last_key:raise ValueError('bar ordering/duplicate')
  if row['open_ms']<previous.get(symbol,0):raise ValueError('overlapping bars')
  last_key=key;previous[symbol]=row['end_ms']
  for field in ('open','high','low','close','volume'):
   v=row[field]
   if type(v) not in (int,float) or not math.isfinite(v) or v<0 or (field!='volume' and v==0):raise ValueError('bar finite/positive numeric')
  if not row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']:raise ValueError('OHLC')
 return rows

def _coverage(rows):
 groups={}
 for row in rows:groups.setdefault(row['symbol'],[]).append(row)
 result=[]
 for symbol,items in sorted(groups.items()):
  interval=items[0]['end_ms']-items[0]['open_ms'];gaps=0
  for i,row in enumerate(items):
   if row['end_ms']-row['open_ms']!=interval:raise ValueError('mixed intervals')
   if i:
    gap=row['open_ms']-items[i-1]['end_ms']
    if gap%interval:raise ValueError('unaligned gap')
    gaps+=gap//interval
  result.append(dict(symbol=symbol,start_ms=items[0]['open_ms'],end_ms=items[-1]['end_ms'],min_available_ms=min(r['available_ms'] for r in items),max_available_ms=max(r['available_ms'] for r in items),interval_ms=interval,gaps=gaps))
 return result

def validate_window(snapshot,start_ms,end_ms):
 """Require each included symbol to span the exact declared exclusive window."""
 if type(start_ms) is not int or type(end_ms) is not int or not 0<=start_ms<end_ms<=2**53-1:raise ValueError('window clocks')
 coverage=_coverage(_bars(snapshot['bars']))
 if any(c['start_ms']!=start_ms or c['end_ms']!=end_ms for c in coverage):raise ValueError('requested window mismatch')
 return snapshot

def load_snapshot(directory,expected_manifest_sha256,expected_source_head,allow_synthetic=False):
 """Verify caller's external byte pin; only explicitly allowed synthetic data."""
 _hex(expected_manifest_sha256,64);_hex(expected_source_head,40)
 root=_safe(directory)
 if not root.is_dir() or {p.name for p in root.iterdir()}!={'manifest.json','bars.json'}:raise ValueError('snapshot membership')
 raw=_read(root/'manifest.json')
 if _digest(raw)!=expected_manifest_sha256:raise ValueError('external manifest hash mismatch')
 m=_json(raw)
 if type(m) is not dict or set(m)!=MANIFEST_KEYS:raise ValueError('manifest schema')
 if m['evidence_class']!='SYNTHETIC':raise ValueError('historical authenticity policy not provisioned')
 if allow_synthetic is not True:raise ValueError('synthetic input must be explicitly allowed')
 if m['schema']!=SCHEMA or m['source_head']!=expected_source_head or m['file']!='bars.json' or m['clock_unit']!='UTC_EPOCH_MS' or m['provenance']!='GENERATED_SYNTHETIC_NOT_MARKET_DATA':raise ValueError('schema/source/provenance mismatch')
 _hex(m['sha256'],64)
 if type(m['bytes']) is not int or not 0<m['bytes']<=MAX_BYTES or type(m['row_count']) is not int or not 1<=m['row_count']<=MAX_ROWS:raise ValueError('manifest bounds')
 data=_read(root/'bars.json')
 if len(data)!=m['bytes'] or _digest(data)!=m['sha256']:raise ValueError('bar hash/size mismatch')
 rows=_bars(_json(data))
 if len(rows)!=m['row_count']:raise ValueError('row count mismatch')
 coverage=_coverage(rows)
 missingness='GAPS_PRESENT' if any(c['gaps'] for c in coverage) else 'NO_INTERNAL_GAPS'
 if _canonical(m['coverage'])!=_canonical(coverage) or m['missingness']!=missingness or m['dataset_id']!=_digest(_canonical(rows)):raise ValueError('coverage/dataset/missingness mismatch')
 return {'manifest':m,'bars':rows}

def write_snapshot(directory,bars,source_head,evidence_class='SYNTHETIC'):
 """Create only a new caller-owned directory; never overwrite existing data."""
 _hex(source_head,40)
 if evidence_class!='SYNTHETIC':raise ValueError('historical authenticity policy not provisioned')
 rows=_bars(bars);coverage=_coverage(rows);data=_canonical(rows)
 if len(data)>MAX_BYTES:raise ValueError('input byte budget')
 root=_safe(directory)
 m=dict(schema=SCHEMA,source_head=source_head,evidence_class='SYNTHETIC',file='bars.json',sha256=_digest(data),bytes=len(data),row_count=len(rows),clock_unit='UTC_EPOCH_MS',provenance='GENERATED_SYNTHETIC_NOT_MARKET_DATA')
 m.update(coverage=coverage,dataset_id=_digest(data),missingness='GAPS_PRESENT' if any(c['gaps'] for c in coverage) else 'NO_INTERNAL_GAPS')
 manifest=_canonical(m)
 root.mkdir() # parent must already exist; existing directories are never reused
 with (root/'bars.json').open('xb') as stream:stream.write(data)
 with (root/'manifest.json').open('xb') as stream:stream.write(manifest)
 return _digest(manifest)
