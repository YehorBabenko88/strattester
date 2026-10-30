"""Atomic, single-flight public request admission. Completion bounds are conservative."""
from contextlib import contextmanager
from collections import deque
from dataclasses import dataclass
import threading,time
class RateStop(RuntimeError):pass
@dataclass(frozen=True)
class Slot:
 sequence:int
 start_ns:int
 endpoint_id:str
class StrictSlidingWindow:
 def __init__(self,*,deadline_ns,clock_ns=time.monotonic_ns,sleep=time.sleep,cancel=lambda:False):
  if type(deadline_ns) is not int or deadline_ns<0:raise ValueError('DEADLINE')
  self.deadline_ns=deadline_ns;self.clock_ns=clock_ns;self.sleep=sleep;self.cancel=cancel
  self._operation=threading.RLock();self._stopped=threading.Event();self._used=0;self._bounds=deque(maxlen=2);self._last=-1;self._inflight=False
 @property
 def used(self):
  with self._operation:return self._used
 def _now(self):
  n=self.clock_ns()
  if type(n) is not int or n<self._last or n<0:raise RateStop('MONOTONIC_CLOCK_INVALID')
  self._last=n;return n
 def check(self):
  with self._operation:
   n=self._now()
   if self.cancel() or self._stopped.is_set():raise RateStop('REQUEST_CANCELLED_OR_STOPPED')
   if n>=self.deadline_ns:raise RateStop('REQUEST_DEADLINE')
   return n
 @contextmanager
 def reserve(self,endpoint_id):
  if endpoint_id not in {'time','instruments','kline'}:raise RateStop('ENDPOINT_RATE_SCOPE')
  acquired=False;ticket_owned=False
  try:
   while not acquired:
    if self.cancel() or self._stopped.is_set():raise RateStop('REQUEST_CANCELLED_OR_STOPPED')
    n=self.clock_ns()
    if type(n) is not int or n>=self.deadline_ns:raise RateStop('REQUEST_DEADLINE')
    acquired=self._operation.acquire(timeout=min(.025,(self.deadline_ns-n)/1e9))
   if self._inflight:raise RateStop('REENTRANT_REQUEST')
   if self._used>=20:raise RateStop('REQUEST_BUDGET')
   while True:
    n=self.check()
    # Last two COMPLETION bounds dominate both transport and HTTP-send starts.
    eligible=self._bounds[0]+1_050_000_000 if len(self._bounds)==2 else n
    if eligible>=self.deadline_ns:raise RateStop('REQUEST_DEADLINE')
    if n>=eligible:break
    self.sleep(min((eligible-n)/1e9,.025))
   self._used+=1;slot=Slot(self._used,self._now(),endpoint_id)
   self._inflight=True;ticket_owned=True
   try:yield slot
   except BaseException:self._stopped.set();raise
   else:self.check()
   finally:
    # Keep ownership through evidence flush; failed attempts consume their slot.
    self._bounds.append(self._now())
  except BaseException:
   self._stopped.set();raise
  finally:
   if ticket_owned:self._inflight=False
   if acquired:self._operation.release()
