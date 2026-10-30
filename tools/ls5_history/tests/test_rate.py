import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest,threading
import strict_rate as r
import rate_verify as v
class Clock:
 def __init__(self):self.n=0;self.lock=threading.Lock()
 def now(self):
  with self.lock:return self.n
 def sleep(self,s):
  with self.lock:self.n+=max(1,int(s*1e9))
class Tests(unittest.TestCase):
 def limiter(self,c,**kw):return r.StrictSlidingWindow(deadline_ns=100_000_000_000,clock_ns=c.now,sleep=c.sleep,**kw)
 def test_third_waits_conservatively(self):
  c=Clock();lim=self.limiter(c);starts=[]
  for _ in range(3):
   with lim.reserve('time') as slot:starts.append(slot.start_ns)
  self.assertGreaterEqual(starts[2]-starts[0],1_050_000_000);self.assertEqual(lim.used,3)
 def test_two_allowed_and_failure_not_refunded(self):
  c=Clock();lim=self.limiter(c)
  with lim.reserve('time'):pass
  with lim.reserve('instruments'):pass
  self.assertEqual(c.now(),0)
  with self.assertRaises(RuntimeError):
   with lim.reserve('kline'):raise RuntimeError('injected')
  self.assertEqual(lim.used,3)
  with self.assertRaises(r.RateStop):
   with lim.reserve('time'):self.fail('must not start')
 def test_concurrency_atomic_shared_budget(self):
  c=Clock();lim=self.limiter(c);out=[];barrier=threading.Barrier(8)
  def work():
   barrier.wait()
   with lim.reserve('kline') as slot:out.append((slot.sequence,slot.start_ns))
  ts=[threading.Thread(target=work) for _ in range(8)]
  for t in ts:t.start()
  for t in ts:t.join(2);self.assertFalse(t.is_alive())
  out.sort();self.assertEqual([n for n,_ in out],list(range(1,9)))
  self.assertTrue(all(out[i][1]-out[i-2][1]>1_000_000_000 for i in range(2,8)))
 def test_deadline_and_cancellation(self):
  c=Clock();lim=r.StrictSlidingWindow(deadline_ns=500_000_000,clock_ns=c.now,sleep=c.sleep)
  for _ in range(2):
   with lim.reserve('time'):pass
  with self.assertRaises(r.RateStop):
   with lim.reserve('time'):self.fail('deadline')
  self.assertEqual(lim.used,2)
  stop=threading.Event();lim=self.limiter(c,cancel=stop.is_set);stop.set()
  with self.assertRaises(r.RateStop):
   with lim.reserve('time'):self.fail('cancelled')
  self.assertEqual(lim.used,0)
 def test_undersleep_is_rechecked(self):
  c=Clock()
  def early_sleep(seconds):
   with c.lock:c.n+=max(1,int(seconds*1e9*.99))
  lim=r.StrictSlidingWindow(deadline_ns=100_000_000_000,clock_ns=c.now,sleep=early_sleep);starts=[]
  for _ in range(3):
   with lim.reserve('time') as slot:starts.append(slot.start_ns)
  self.assertGreaterEqual(starts[2]-starts[0],1_050_000_000)
 def test_nested_reservation_rejected(self):
  c=Clock();lim=self.limiter(c)
  with self.assertRaises(r.RateStop):
   with lim.reserve('time'):
    with lim.reserve('kline'):self.fail('nested admission')
  self.assertEqual(lim.used,1)
 def test_slow_completion_bounds_http_send(self):
  c=Clock();lim=self.limiter(c);starts=[]
  with lim.reserve('time'):
   c.sleep(.9);starts.append(c.now())
  with lim.reserve('kline'):starts.append(c.now())
  with lim.reserve('instruments'):starts.append(c.now())
  self.assertGreaterEqual(starts[2]-starts[0],1_050_000_000)
 def test_verifier_three_and_boundaries(self):
  def events(times):return [dict(sequence=i+1,endpoint_id='time',attempt_start_ns=t,http_start_ns=t,completed_ns=t,duration_ns=0,http_status=200,budget_used=i+1,budget_limit=20,pid=20,nonce='a'*32,utc_start='2026-10-30T00:00:00+00:00') for i,t in enumerate(times)]
  def check(times):
   es=events(times);keys={'sequence','endpoint_id','attempt_start_ns','utc_start','budget_used','budget_limit','pid','nonce'}
   return v.verify(es,len(es),20,'a'*32,[{k:e[k] for k in keys} for e in es])
  for times in [[0,500_000_000,993_945_000],[0,0,1_000_000_000]]:self.assertEqual(check(times)['status'],'RATE_BUDGET_FAIL')
  self.assertEqual(check([0,0,1_050_000_000])['status'],'RATE_BUDGET_PASS')
  self.assertEqual(check([0,0])['status'],'RATE_BUDGET_PASS')
if __name__=='__main__':unittest.main()
