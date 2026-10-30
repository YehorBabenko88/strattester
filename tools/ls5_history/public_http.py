"""Fixed-host standard-library HTTPS, no proxies/auth/cookies/redirects/retries."""
import hashlib,http.client,ipaddress,json,socket,ssl,time
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
HOST='api.bybit.com';PATHS={'/v5/market/time','/v5/market/instruments-info','/v5/market/kline'}
class NetworkPolicy:
 def __init__(self):self.enabled=False;self.ips=set();self.dns=0;self.connects=0
 def audit(self,event,args):
  if not event.startswith('socket.'):return
  if event=='socket.gethostname':return
  if not self.enabled:raise RuntimeError('NETWORK_NOT_ADMITTED')
  if event=='socket.getaddrinfo':
   if args[0]!=HOST or args[1]!=443 or self.dns>=21:raise RuntimeError('DNS_NOT_ADMITTED')
   self.dns+=1;return
  if event=='socket.__new__':
   if args[1] not in (socket.AF_INET,socket.AF_INET6) or args[2]!=socket.SOCK_STREAM:raise RuntimeError('SOCKET_NOT_ADMITTED')
   return
  if event=='socket.connect':
   target=args[1]
   if not isinstance(target,tuple) or len(target)<2 or target[0] not in self.ips or target[1]!=443 or self.connects>=20:raise RuntimeError('EGRESS_NOT_ADMITTED')
   self.connects+=1;return
  raise RuntimeError('SOCKET_OPERATION_DENIED')
 def resolve(self):
  self.enabled=True
  records=socket.getaddrinfo(HOST,443,type=socket.SOCK_STREAM)
  addresses={r[4][0] for r in records}
  if not addresses or len(addresses)>16 or any(not ipaddress.ip_address(x).is_global for x in addresses):raise RuntimeError('DNS_ADDRESS_POLICY')
  self.ips=addresses

def retry_hint(value,now):
 if not value:return None
 try:v=float(value)
 except (ValueError,TypeError):
  try:v=parsedate_to_datetime(value).timestamp()-now
  except (ValueError,TypeError,OverflowError):return None
 return min(v,86400.0) if 0<=v<=86400 else None
class PublicHTTP:
 def __init__(self,policy,cafile,record,decode,limiter,on_start):
  self.policy=policy;self.context=ssl.create_default_context(cafile=cafile);self.record=record;self.decode=decode;self.limiter=limiter;self.on_start=on_start;self.bytes=0
 def _timeout(self,cap):
  n=self.limiter.check();return min(cap,(self.limiter.deadline_ns-n)/1e9)
 @property
 def count(self):return self.limiter.used
 def __call__(self,path,params):
  from urllib.parse import urlencode
  if path not in PATHS or type(params) is not dict or any(type(v) not in (str,int) for v in params.values()):raise RuntimeError('ENDPOINT_POLICY')
  endpoint_id={'/v5/market/time':'time','/v5/market/instruments-info':'instruments','/v5/market/kline':'kline'}[path]
  with self.limiter.reserve(endpoint_id) as slot:
   start=datetime.now(timezone.utc).isoformat();conn=None;response=None
   meta=dict(id=slot.sequence,host=HOST,path=path,params=params,endpoint_id=endpoint_id,attempt_start_ns=slot.start_ns,http_start_ns=None,completed_ns=None,duration_ns=None,budget_used=slot.sequence,budget_limit=20,observed_start_utc=start,status=None,tls_verified=False,peer_ip=None,body_sha256=None,body_bytes=0,received_body_bytes=0,body_complete=False,retry_after_seconds=None,outcome='REQUEST_FAILED')
   try:
    self.on_start(dict(sequence=slot.sequence,endpoint_id=endpoint_id,attempt_start_ns=slot.start_ns,utc_start=start,budget_used=slot.sequence,budget_limit=20))
    self.limiter.check()
    conn=http.client.HTTPSConnection(HOST,443,timeout=self._timeout(3),context=self.context);conn.connect();conn.sock.settimeout(self._timeout(5))
    peer=conn.sock.getpeername()
    if peer[0] not in self.policy.ips or peer[1]!=443:raise RuntimeError('TLS_PEER_POLICY')
    meta['peer_ip']=peer[0];meta['tls_verified']=True
    self.limiter.check();meta['http_start_ns']=self.limiter.clock_ns()
    conn.request('GET',path+('?' +urlencode(params) if params else ''),headers={'Accept':'application/json','Accept-Encoding':'identity','User-Agent':'Strattester-Public-Data-Smoke/2'})
    conn.sock.settimeout(self._timeout(5));response=conn.getresponse();meta['status']=response.status;meta['retry_after_seconds']=retry_hint(response.getheader('Retry-After'),time.time())
    if response.status!=200:raise RuntimeError('HTTP_STOP_NO_RETRY')
    if response.getheader('Content-Encoding','identity').lower()!='identity':raise RuntimeError('ENCODING_POLICY')
    body=bytearray()
    while True:
     self.limiter.check();chunk=response.read(65536)
     self.limiter.check()
     if not chunk:break
     self.bytes+=len(chunk);meta['received_body_bytes']+=len(chunk)
     if len(body)+len(chunk)>2*1024*1024 or self.bytes>8*1024*1024:raise RuntimeError('RESPONSE_BYTE_BUDGET')
     body.extend(chunk)
    meta['body_complete']=True;meta['body_bytes']=len(body);meta['body_sha256']=hashlib.sha256(body).hexdigest()
    result=self.decode(body);self.limiter.check();meta['outcome']='SUCCESS';return result
   finally:
    try:
     try:
      if response is not None:response.close()
     finally:
      if conn is not None:conn.close()
    finally:
     end=self.limiter.clock_ns();meta['completed_ns']=end;meta['duration_ns']=end-slot.start_ns
     meta['observed_end_utc']=datetime.now(timezone.utc).isoformat();self.record(meta)
