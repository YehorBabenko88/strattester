"""Read-only Grid v1.1 integrity inspection; never native admission or training."""
import math
import os
import stat
from .adapter import _safe,_hex,_json,_canonical,_digest

LIMIT=8*1024*1024
TOP={'schema','request','source','evidence_class','rows','source_receipts','execution_authority','trading_authorized','watermark_ms','dataset_id','dataset_fingerprint'}
REQUEST={'schema','venue','market_type','symbol','units','start_ms','end_ms','as_of_ms','max_age_ms'}
ROW={'open','high','low','close','volume','event_start_ms','event_end_ms','available_at_ms','revision','source_event_start_ms','source_event_end_ms','watermark_ms','source_receipt_hash'}

def need(value,message):
 if not value:raise ValueError(message)
def clock(value):need(type(value) is int and 0<=value<=2**53-1,'integer UTC epoch millisecond clock required')
def text(value):need(type(value) is str and bool(value) and value.strip()==value,'identity text required')
def inspect_grid_v11(path,expected_file_sha256,expected_source_head):
 """Return integrity/coverage facts only, retaining original file bytes untouched."""
 _hex(expected_file_sha256,64);_hex(expected_source_head,40);p=_safe(path)
 with p.open('rb') as stream:
  info=os.fstat(stream.fileno());need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=LIMIT,'file/link/byte budget')
  raw=stream.read(LIMIT+1)
 need(len(raw)<=LIMIT,'byte budget');need(_digest(raw)==expected_file_sha256,'external byte hash mismatch')
 e=_json(raw);need(type(e) is dict and set(e)==TOP,'envelope schema')
 need(e['schema']=='grid.history.v1.1','native version required')
 need(e['execution_authority'] is False and e['trading_authorized'] is False,'research authority boundary')
 need(e['evidence_class'] in ('SYNTHETIC','HISTORICAL'),'evidence class')
 s=e['source'];need(type(s) is dict and set(s)=={'identity','source_revision','epoch'},'source schema')
 for value in s.values():text(value)
 _hex(s['source_revision'],40);need(s['source_revision']==expected_source_head,'source HEAD mismatch')
 q=e['request'];need(type(q) is dict and set(q)==REQUEST and q['schema']=='grid.history.request.v1','request schema')
 for key in ('venue','market_type','symbol'):text(q[key])
 need(type(q['units']) is dict and set(q['units'])=={'price','volume'},'explicit unit schema')
 for value in q['units'].values():text(value)
 for key in ('start_ms','end_ms','as_of_ms','max_age_ms'):clock(q[key])
 start,end=q['start_ms'],q['end_ms'];need(start%60000==end%60000==0 and 1<=(end-start)//60000<=2000,'minute interval bounds')
 need(q['as_of_ms']>=end and q['as_of_ms']-end<=q['max_age_ms'],'as-of/staleness')
 rows=e['rows'];need(type(rows) is list and len(rows)==(end-start)//60000,'continuous bounded rows')
 pins=e['source_receipts'];need(type(pins) is list and len(pins)==len(rows),'receipt membership')
 seen=set()
 for i,row in enumerate(rows):
  need(type(row) is dict and set(row)==ROW,'row schema')
  for key in ('event_start_ms','event_end_ms','available_at_ms','source_event_start_ms','source_event_end_ms','watermark_ms'):clock(row[key])
  lo=start+i*60000;hi=lo+60000
  need(row['event_start_ms']==lo and row['event_end_ms']==hi,'exclusive minute boundaries/order')
  need(lo<=row['source_event_start_ms']<=row['source_event_end_ms']<hi,'source event clock')
  need(hi<=row['watermark_ms']<=row['available_at_ms']<=q['as_of_ms'],'availability/watermark ordering')
  _hex(row['revision'],64);_hex(row['source_receipt_hash'],64);_hex(pins[i],64)
  need(row['revision'] not in seen,'duplicate revision');seen.add(row['revision'])
  need(pins[i]==row['source_receipt_hash'],'receipt binding mismatch')
  for key in ('open','high','low','close','volume'):
   v=row[key];need(type(v) in (int,float) and math.isfinite(v) and (v>=0 if key=='volume' else v>0),'finite OHLCV')
  need(row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high'],'OHLC shape')
 clock(e['watermark_ms']);need(e['watermark_ms']==max(r['watermark_ms'] for r in rows),'aggregate watermark')
 content=dict(schema='grid.dataset.v1.1',source=s,identity={k:q[k] for k in ('venue','market_type','symbol','units')},timeframe='1m',representation='historical_aggregate',evidence_class=e['evidence_class'],rows=rows,source_receipts=pins)
 _hex(e['dataset_id'],64);_hex(e['dataset_fingerprint'],64)
 need(_digest(_canonical(content))==e['dataset_id'],'dataset content hash mismatch')
 need(_digest(_canonical({k:v for k,v in e.items() if k!='dataset_fingerprint'}))==e['dataset_fingerprint'],'envelope hash mismatch')
 return dict(schema='mwi.local.grid.v11.inspection.v1',status='HISTORICAL_UNATTESTED' if e['evidence_class']=='HISTORICAL' else 'SYNTHETIC',training_eligible=False,blockers=['RECEIPT_AUTHENTICITY_NOT_PROVISIONED','NATIVE_TRAINING_ADMISSION_NOT_IMPLEMENTED'],file_sha256=expected_file_sha256,source_head=expected_source_head,dataset_id=e['dataset_id'],dataset_fingerprint=e['dataset_fingerprint'],row_count=len(rows),identity={k:q[k] for k in ('venue','market_type','symbol','units')},coverage=dict(start_ms=start,end_ms=end,interval_ms=60000,gaps=0,min_available_ms=min(r['available_at_ms'] for r in rows),max_available_ms=max(r['available_at_ms'] for r in rows),as_of_ms=q['as_of_ms']),source=dict(s),clock_unit='UTC_EPOCH_MS',source_authenticity='NOT_EVALUATED',receipt_contents='NOT_PROVIDED_HASH_BINDINGS_ONLY')
