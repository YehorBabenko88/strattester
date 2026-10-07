import pytest
from strattester.marketdata.bybit_client import BybitClient,RetryPolicy,BybitAccessError,RetryableBybitError

class Response:
    def __init__(self,status,payload=None,headers=None): self.status_code=status; self.payload=payload or {'retCode':0,'result':{}};self.headers=headers or {}
    def json(self): return self.payload
class Session:
    def __init__(self,statuses): self.statuses=list(statuses); self.calls=0
    def get(self,*a,**k): self.calls+=1; return Response(self.statuses.pop(0))

def test_403_fails_without_retry():
    s=Session([403]); c=BybitClient(session=s,sleep=lambda _:None)
    with pytest.raises(BybitAccessError): c.get('/x')
    assert s.calls==1

def test_429_retries_then_succeeds():
    s=Session([429,200]); sleeps=[]
    c=BybitClient(session=s,sleep=sleeps.append,retry=RetryPolicy(attempts=3,base_delay=.1))
    assert c.get('/x')['retCode']==0
    assert s.calls==2 and sleeps==[.1]

def test_5xx_exhaustion_is_retryable():
    s=Session([500,503])
    c=BybitClient(session=s,sleep=lambda _:None,retry=RetryPolicy(attempts=2))
    with pytest.raises(RetryableBybitError): c.get('/x')


def test_retry_after_is_honored_but_bounded():
    class S:
        calls=0
        def get(self,*a,**k):
            self.calls+=1
            return Response(429,headers={'Retry-After':'99'}) if self.calls==1 else Response(200)
    s=S();sleeps=[];c=BybitClient(session=s,sleep=sleeps.append,retry=RetryPolicy(2,.1,2))
    c.get('/x');assert sleeps==[2]

def test_bybit_rate_limit_retcode_is_retryable():
    class S:
        calls=0
        def get(self,*a,**k):
            self.calls+=1
            return Response(200,{'retCode':10006,'retMsg':'Too many visits'}) if self.calls==1 else Response(200)
    s=S();c=BybitClient(session=s,sleep=lambda _:None,retry=RetryPolicy(2,0,1))
    assert c.get('/x')['retCode']==0 and s.calls==2

def test_invalid_retry_policy_fails_before_network():
    s=Session([200]);c=BybitClient(session=s,retry=RetryPolicy(0,1,1))
    with pytest.raises(ValueError):c.get('/x')
    assert s.calls==0
