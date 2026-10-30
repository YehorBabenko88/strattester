"""Independent post-run oracle; does not import the limiter or transport."""
from datetime import datetime,timezone
def verify(events,used,pid,nonce,starts=None):
 fail=lambda reason:dict(status='RATE_BUDGET_FAIL',reason=reason,budget_limit=20,budget_used=used)
 if type(used) is not int or not 1<=used<=20 or type(events) is not list or len(events)!=used:return fail('COUNT_OR_BUDGET')
 if type(starts) is not list or len(starts)!=used:return fail('START_LEDGER_INCOMPLETE')
 attempts=[];http=[]
 required={'sequence','endpoint_id','attempt_start_ns','http_start_ns','completed_ns','duration_ns','http_status','budget_used','budget_limit','pid','nonce','utc_start'}
 for i,e in enumerate(events):
  if not isinstance(e,dict) or set(e)!=required:return fail('FIELDS')
  keys={'sequence','endpoint_id','attempt_start_ns','utc_start','budget_used','budget_limit','pid','nonce'}
  if type(starts[i]) is not dict or set(starts[i])!=keys or any(type(starts[i][k]) is not type(e[k]) or starts[i][k]!=e[k] for k in keys):return fail('START_LEDGER_BINDING')
  if any(type(e.get(k)) is not int for k in ('sequence','budget_used','budget_limit','pid')) or type(e.get('nonce')) is not str or type(e.get('endpoint_id')) is not str:return fail('FIELD_TYPES')
  try:
   stamp=datetime.fromisoformat(e.get('utc_start',''))
   if stamp.utcoffset()!=timezone.utc.utcoffset(stamp):return fail('UTC_TIMESTAMP')
  except (TypeError,ValueError):return fail('UTC_TIMESTAMP')
  if not isinstance(e,dict) or type(e.get('sequence')) is not int or e['sequence']!=i+1 or e.get('endpoint_id') not in ('time','instruments','kline') or e.get('pid')!=pid or e.get('nonce')!=nonce or e.get('budget_used')!=i+1 or e.get('budget_limit')!=20:return fail('IDENTITY_OR_SEQUENCE')
  a=e.get('attempt_start_ns');b=e.get('completed_ns');send=e.get('http_start_ns')
  if type(a) is not int or type(b) is not int or a<0 or b<a or type(e.get('duration_ns')) is not int or e['duration_ns']!=b-a or type(e.get('utc_start')) is not str:return fail('TIMESTAMP_OR_DURATION')
  if e.get('http_status') is not None and (type(e['http_status']) is not int or not 100<=e['http_status']<=599):return fail('HTTP_STATUS')
  attempts.append(a)
  if send is not None:
   if type(send) is not int or not a<=send<=b:return fail('HTTP_START')
   http.append(send)
  elif e.get('http_status') is not None:return fail('MISSING_HTTP_START')
 for values in (attempts,http):
  if values!=sorted(values):return fail('START_ORDER')
  # Closed one-second boundary: even an exact1s triple fails conservatively.
  if any(values[j]-values[j-2]<=1_000_000_000 for j in range(2,len(values))):return fail('SLIDING_WINDOW')
 return dict(status='RATE_BUDGET_PASS',budget_used=used,budget_remaining=20-used,budget_limit=20,attempts_verified=len(attempts),http_starts_verified=len(http),window_ns=1_000_000_000,scope='RECORDED_MONOTONIC_ATTEMPT_AND_HTTP_STARTS')
