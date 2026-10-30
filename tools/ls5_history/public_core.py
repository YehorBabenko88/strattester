"""Public data-only smoke contracts. All IO supplied explicitly; no strategies."""
import hashlib,json,math,re
from decimal import Decimal
HOST='api.bybit.com'
PATHS={'/v5/market/time','/v5/market/instruments-info','/v5/market/kline'}
def strict(data):
 def pairs(items):
  out={}
  for k,v in items:
   if k in out:raise ValueError('DUPLICATE_JSON')
   out[k]=v
  return out
 def bad(_):raise ValueError('NONFINITE_JSON')
 value=json.loads(data,object_pairs_hook=pairs,parse_constant=bad)
 if type(value) is not dict or type(value.get('retCode')) is not int or value['retCode']!=0:raise ValueError('PUBLIC_API_ERROR')
 return value
def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def discover(call):
 cursor='';seen_cursors=set();seen_symbols=set();records=[]
 for page in range(4):
  params=dict(category='linear',status='Trading',limit=1000)
  if cursor:params['cursor']=cursor
  data=call('/v5/market/instruments-info',params);r=data.get('result',{})
  if r.get('category')!='linear' or type(r.get('list')) is not list or len(r['list'])>1000:raise ValueError('UNIVERSE_SCHEMA')
  for v in r['list']:
   if type(v) is not dict or type(v.get('symbol')) is not str or not re.fullmatch('[A-Z0-9_.-]{1,80}',v['symbol']) or v['symbol'] in seen_symbols or v.get('status')!='Trading':raise ValueError('UNIVERSE_IDENTITY')
   seen_symbols.add(v['symbol'])
   fields=[v.get(k) for k in ('symbol','launchTime','contractType','settleCoin','deliveryTime','marketRegion')]
   if any(x is not None and (type(x) is not str or len(x)>80) for x in fields):raise ValueError('METADATA_BOUND')
   records.append(dict(fields=fields,page=page))
  next_cursor=r.get('nextPageCursor','')
  if type(next_cursor) is not str or len(next_cursor)>4096:raise ValueError('CURSOR_SCHEMA')
  if not next_cursor:
   if not records:raise ValueError('EMPTY_UNIVERSE')
   if len(encoded(records))>384*1024:raise ValueError('UNIVERSE_STORAGE_BUDGET')
   return records
  if not r['list'] or next_cursor==cursor or next_cursor in seen_cursors:raise ValueError('CURSOR_REPLAY')
  seen_cursors.add(cursor);cursor=next_cursor
 raise ValueError('UNIVERSE_PAGE_BUDGET')
def window(server_ms):
 if type(server_ms) is not int or server_ms<=0:raise ValueError('SERVER_TIME')
 end=((server_ms-60000)//300000)*300000
 return end-900000,end

def choose(records,start):
 selected=[]
 for row in sorted(records,key=lambda r:r['fields'][0]):
  symbol,launch,contract,settle,delivery,region=row['fields']
  if contract in ('LinearPerpetual','LinearFutures') and launch and launch.isdigit() and 0<int(launch)<=start and not region and (not delivery or delivery=='0' or delivery.isdigit() and int(delivery)>=start+900000):selected.append(symbol)
  if len(selected)==3:break
 if not selected:raise ValueError('NO_ELIGIBLE_INSTRUMENT')
 return selected

def candles(call,symbol,tf,start,end):
 step=60000 if tf=='1m' else 300000 if tf=='5m' else 0
 if not step:raise ValueError('TIMEFRAME')
 rows={};upper=end-1
 for _ in range(2):
  data=call('/v5/market/kline',dict(category='linear',symbol=symbol,interval='1' if tf=='1m' else '5',start=start,end=upper,limit=200))
  r=data.get('result',{})
  if r.get('category')!='linear' or r.get('symbol')!=symbol or type(r.get('list')) is not list or len(r['list'])>200:raise ValueError('CANDLE_IDENTITY')
  batch=r['list']
  if not batch:break
  last=None
  for v in batch:
   if type(v) is not list or len(v)!=7 or any(type(x) is not str or len(x)>80 for x in v) or not v[0].isdigit():raise ValueError('CANDLE_SCHEMA')
   t=int(v[0]);nums=[Decimal(x) for x in v[1:]]
   if not all(x.is_finite() for x in nums) or not all(math.isfinite(float(x)) for x in nums):raise ValueError('CANDLE_NONFINITE')
   o,h,l,c,volume,turnover=nums
   if min(o,h,l,c)<=0 or not l<=o<=h or not l<=c<=h or min(volume,turnover)<0 or t%step or t<start or t>upper or t+step>end or (last is not None and t>=last) or t in rows:raise ValueError('CANDLE_QUALITY_OR_GRID')
   rows[t]=(t,*[float(x) for x in nums]);last=t
  oldest=min(rows);upper=oldest-step
  if upper<start:break
 expected=list(range(start,end,step));missing=[t for t in expected if t not in rows]
 status='MISSING' if not rows else 'PARTIAL' if missing else 'READY'
 return [rows[t] for t in sorted(rows)],dict(state=status,expected=len(expected),actual=len(rows),missing=missing,strategy_execution='NOT_AUTHORIZED',historical_availability='UNKNOWN_BEFORE_OBSERVATION')
