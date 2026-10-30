import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest,threading,time
from unittest.mock import patch
import public_http as h
import public_core as core
import strict_rate as rate
import rate_verify
from test_rate import Clock
class Tests(unittest.TestCase):
 def test_http_error_timeout_cancel_never_retries(self):
  for mode in (403,429,500,'timeout','cancel','deadline'):
   with self.subTest(mode=mode):
    clock=Clock();stop=threading.Event();lim=rate.StrictSlidingWindow(deadline_ns=2_000_000_000,clock_ns=clock.now,sleep=clock.sleep,cancel=stop.is_set);records=[];created=[];sent=[]
    class Sock:
     def settimeout(self,n):pass
     def getpeername(self):return ('8.8.8.8',443)
    class Response:
     status=mode if type(mode) is int else 200
     def getheader(self,k,default=None):return '3' if k=='Retry-After' else default
     def close(self):pass
    class Conn:
     def __init__(self,*a,**kw):created.append(a);self.sock=Sock()
     def connect(self):
      if mode=='timeout':raise TimeoutError('injected')
      if mode=='cancel':stop.set()
      if mode=='deadline':clock.sleep(3)
     def request(self,*a,**kw):sent.append(a)
     def getresponse(self):return Response()
     def close(self):pass
    client=object.__new__(h.PublicHTTP);client.policy=h.NetworkPolicy();client.policy.ips={'8.8.8.8'};client.context=None;client.limiter=lim;client.record=records.append;client.on_start=lambda event:None;client.decode=core.strict;client.bytes=0
    with patch.object(h.http.client,'HTTPSConnection',Conn):
     with self.assertRaises(Exception):client('/v5/market/time',{})
     with self.assertRaises(rate.RateStop):client('/v5/market/instruments-info',{'category':'linear'})
    self.assertEqual(len(created),1);self.assertEqual(lim.used,1);self.assertEqual(len(records),1)
    if mode in ('timeout','cancel','deadline'):self.assertEqual(sent,[])
 def test_total_budget_shared_all_endpoints(self):
  clock=Clock();lim=rate.StrictSlidingWindow(deadline_ns=100_000_000_000,clock_ns=clock.now,sleep=clock.sleep)
  for i in range(20):
   with lim.reserve(('time','instruments','kline')[i%3]):pass
  with self.assertRaises(rate.RateStop):
   with lim.reserve('time'):self.fail('21st request')
  self.assertEqual(lim.used,20)
 def test_cancellation_during_slot_wait(self):
  clock=Clock();lim=rate.StrictSlidingWindow(deadline_ns=10_000_000_000,clock_ns=clock.now,sleep=clock.sleep,cancel=lambda:clock.now()>=25_000_000)
  for i in range(2):
   with lim.reserve('time'):pass
  with self.assertRaises(rate.RateStop):
   with lim.reserve('kline'):self.fail('cancelled while waiting')
  self.assertEqual(lim.used,2)
 def test_recorded_missing_monotonic_is_failure(self):
  self.assertEqual(rate_verify.verify([dict(sequence=1)],1,20,'a'*32)['status'],'RATE_BUDGET_FAIL')
 def test_eof_and_evidence_crossing_deadline_stop(self):
  for mode in ('eof','evidence'):
   with self.subTest(mode=mode):
    clock=Clock();lim=rate.StrictSlidingWindow(deadline_ns=2_000_000_000,clock_ns=clock.now,sleep=clock.sleep)
    class Sock:
     def settimeout(self,n):pass
     def getpeername(self):return ('8.8.8.8',443)
    class Response:
     status=200
     def __init__(self):self.n=0
     def getheader(self,k,default=None):return default
     def read(self,n):
      self.n+=1
      if self.n==1:return b'{"retCode":0}'
      if mode=='eof':clock.sleep(3)
      return b''
     def close(self):pass
    class Conn:
     def __init__(self,*a,**kw):self.sock=Sock()
     def connect(self):pass
     def request(self,*a,**kw):pass
     def getresponse(self):return Response()
     def close(self):pass
    client=object.__new__(h.PublicHTTP);client.policy=h.NetworkPolicy();client.policy.ips={'8.8.8.8'};client.context=None;client.limiter=lim;client.on_start=lambda _:None;client.record=lambda _:clock.sleep(3) if mode=='evidence' else None;client.decode=core.strict;client.bytes=0
    with patch.object(h.http.client,'HTTPSConnection',Conn):
     with self.assertRaises(rate.RateStop):client('/v5/market/time',{})
 def test_connection_close_response_body_still_readable(self):
  clock=Clock();lim=rate.StrictSlidingWindow(deadline_ns=2_000_000_000,clock_ns=clock.now,sleep=clock.sleep);closed=[]
  class Sock:
   def settimeout(self,n):pass
   def getpeername(self):return ('8.8.8.8',443)
  class Response:
   status=200
   def __init__(self):self.n=0
   def getheader(self,k,default=None):return default
   def read(self,n):self.n+=1;return b'{"retCode":0}' if self.n==1 else b''
   def close(self):closed.append('response')
  class Conn:
   def __init__(self,*a,**kw):self.sock=Sock()
   def connect(self):pass
   def request(self,*a,**kw):pass
   def getresponse(self):self.sock=None;return Response()
   def close(self):closed.append('connection')
  client=object.__new__(h.PublicHTTP);client.policy=h.NetworkPolicy();client.policy.ips={'8.8.8.8'};client.context=None;client.limiter=lim;client.on_start=lambda _:None;client.record=lambda _:None;client.decode=core.strict;client.bytes=0
  with patch.object(h.http.client,'HTTPSConnection',Conn):self.assertEqual(client('/v5/market/time',{})['retCode'],0)
 def test_incomplete_pagination_stops_without_partial_universe(self):
  calls=[]
  def fake(path,params):
   calls.append((path,dict(params)));i=len(calls)
   return dict(result=dict(category='linear',list=[dict(symbol='A'+str(i),status='Trading',contractType='LinearPerpetual',launchTime='1')],nextPageCursor='cursor'+str(i)))
  with self.assertRaisesRegex(ValueError,'UNIVERSE_PAGE_BUDGET'):core.discover(fake)
  self.assertEqual(len(calls),4)
if __name__=='__main__':unittest.main()
