from __future__ import annotations
from dataclasses import dataclass
import time
import requests

class RetryableBybitError(RuntimeError): pass
class BybitAccessError(RuntimeError): pass
class BybitResponseError(RuntimeError): pass

@dataclass(frozen=True)
class RetryPolicy:
    attempts:int=5
    base_delay:float=1.0
    max_delay:float=30.0

class BybitClient:
    def __init__(self,base_url='https://api.bybit.com',session=None,sleep=time.sleep,retry=RetryPolicy()):
        self.base_url=base_url.rstrip('/'); self.session=session or requests.Session(); self.sleep=sleep; self.retry=retry

    def get(self,path,params=None):
        last=None
        for attempt in range(self.retry.attempts):
            try:
                r=self.session.get(self.base_url+path,params=params,timeout=30)
            except requests.RequestException as exc:
                last=RetryableBybitError(str(exc))
            else:
                if r.status_code==403: raise BybitAccessError('Bybit access forbidden (HTTP 403)')
                if r.status_code==429 or 500<=r.status_code<600:
                    last=RetryableBybitError(f'Bybit temporary HTTP {r.status_code}')
                elif r.status_code>=400: raise BybitResponseError(f'Bybit HTTP {r.status_code}')
                else:
                    data=r.json()
                    if data.get('retCode',0)!=0: raise BybitResponseError(str(data.get('retMsg','Bybit error')))
                    return data
            if attempt+1<self.retry.attempts:
                self.sleep(min(self.retry.base_delay*(2**attempt),self.retry.max_delay))
        raise last or RetryableBybitError('Bybit request failed')

    def fetch_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000):
        data=self.get('/v5/market/kline',{'category':'linear','symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])
