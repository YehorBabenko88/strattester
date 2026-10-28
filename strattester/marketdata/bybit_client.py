from __future__ import annotations
from dataclasses import dataclass
import time
import json
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
    def __init__(self,base_url='https://api.bybit.com',session=None,sleep=time.sleep,retry=RetryPolicy(),*,before_request=None,cancel=lambda:False,timeout=30,max_response_bytes=8*1024*1024):
        self.base_url=base_url.rstrip('/'); self.session=session or requests.Session(); self.sleep=sleep; self.retry=retry
        self.before_request=before_request;self.cancel=cancel;self.timeout=timeout
        if type(max_response_bytes) is not int or not 1<=max_response_bytes<=16*1024*1024:raise ValueError('response byte budget')
        self.max_response_bytes=max_response_bytes

    def _response_json(self,response):
        if hasattr(response,'iter_content'):
            content=bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                if self.cancel():raise InterruptedError('Bybit response cancelled')
                if len(content)+len(chunk)>self.max_response_bytes:raise BybitResponseError('response byte budget')
                content.extend(chunk)
            def pairs(items):
                value={}
                for key,item in items:
                    if key in value:raise BybitResponseError('duplicate response JSON key')
                    value[key]=item
                return value
            data=json.loads(content,object_pairs_hook=pairs)
        else:
            # Explicit injected synthetic sessions may expose only json().
            data=response.json()
            if len(json.dumps(data,allow_nan=False).encode())>self.max_response_bytes:raise BybitResponseError('response byte budget')
        if type(data) is not dict or type(data.get('retCode')) is not int:raise BybitResponseError('response schema')
        return data

    def get(self,path,params=None):
        if self.retry.attempts<1 or self.retry.base_delay<0 or self.retry.max_delay<0:
            raise ValueError("invalid retry policy")
        last=None
        for attempt in range(self.retry.attempts):
            if self.cancel():raise InterruptedError('Bybit request cancelled')
            if self.before_request is not None:self.before_request()
            try:
                r=self.session.get(self.base_url+path,params=params,timeout=self.timeout,stream=True,allow_redirects=False)
            except requests.RequestException as exc:
                last=RetryableBybitError(str(exc))
            else:
                if 300<=r.status_code<400:
                    if hasattr(r,'close'):r.close()
                    raise BybitResponseError('Bybit redirect prohibited')
                if r.status_code==403:
                    if hasattr(r,'close'):r.close()
                    raise BybitAccessError('Bybit access forbidden (HTTP 403)')
                if r.status_code==429 or 500<=r.status_code<600:
                    if hasattr(r,'close'):r.close()
                    last=RetryableBybitError(f'Bybit temporary HTTP {r.status_code}')
                    retry_after=None
                    try: retry_after=float(r.headers.get('Retry-After')) if r.headers.get('Retry-After') else None
                    except (TypeError,ValueError): retry_after=None
                elif r.status_code>=400:
                    if hasattr(r,'close'):r.close()
                    raise BybitResponseError(f'Bybit HTTP {r.status_code}')
                else:
                    try:data=self._response_json(r)
                    finally:
                        if hasattr(r,'close'):r.close()
                    code=int(data.get('retCode',0) or 0)
                    if code in (10006,10429):
                        last=RetryableBybitError(str(data.get('retMsg','Bybit rate limit')))
                        retry_after=None
                    elif code!=0:
                        raise BybitResponseError(str(data.get('retMsg','Bybit error')))
                    else:
                        return data
            if attempt+1<self.retry.attempts:
                exponential=self.retry.base_delay*(2**attempt)
                hinted=retry_after if 'retry_after' in locals() and retry_after is not None and retry_after>=0 else 0
                delay=min(max(exponential,hinted),self.retry.max_delay)
                if self.before_request is None:self.sleep(delay)
                else:
                    while delay>0:
                        if self.cancel():raise InterruptedError('Bybit retry cancelled')
                        part=min(delay,.05);self.sleep(part);delay-=part
                retry_after=None
        raise last or RetryableBybitError('Bybit request failed')

    def fetch_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000,*,category='linear'):
        data=self.get('/v5/market/kline',{'category':category,'symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])


    def fetch_instruments(self,category='linear',*,max_pages=100,max_instruments=20000):
        if category not in ('linear','inverse','spot') or type(max_pages) is not int or not 1<=max_pages<=1000 or type(max_instruments) is not int or not 1<=max_instruments<=100000:
            raise ValueError('instrument discovery admission')
        instruments=[];cursor='';cursors=set();symbols=set()
        for page in range(max_pages):
            params={'category':category,'status':'Trading'}
            if category!='spot':params['limit']=1000
            if cursor:params['cursor']=cursor
            cursors.add(cursor)
            data=self.get('/v5/market/instruments-info',params)
            result=data.get('result',{})
            rows=result.get('list')
            if type(rows) is not list or result.get('category')!=category:raise BybitResponseError('malformed instrument page market identity')
            for row in rows:
                if type(row) is not dict or type(row.get('symbol')) is not str or not row['symbol'] or row['symbol'] in symbols:
                    raise BybitResponseError('duplicate or malformed instrument identity')
                symbols.add(row['symbol']);instruments.append(dict(row))
                if len(instruments)>max_instruments:raise BybitResponseError('instrument count budget')
            cursor=result.get('nextPageCursor','')
            if type(cursor) is not str or len(cursor)>4096:raise BybitResponseError('invalid pagination cursor')
            if not cursor:return instruments
            if category=='spot' or cursor in cursors or not rows:raise BybitResponseError('incomplete or repeated instrument cursor')
        raise BybitResponseError('instrument page budget')

    def fetch_linear_instruments(self):
        instruments=[row for row in self.fetch_instruments('linear')
                     if row.get('status')=='Trading' and row.get('quoteCoin')=='USDT'
                     and row.get('contractType')=='LinearPerpetual']
        return instruments

    def fetch_linear_symbols(self):
        return {x.get('symbol') for x in self.fetch_linear_instruments() if x.get('symbol')}



    def fetch_mark_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000,*,category='linear'):
        data=self.get('/v5/market/mark-price-kline',{'category':category,'symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_index_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000,*,category='linear'):
        data=self.get('/v5/market/index-price-kline',{'category':category,'symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_premium_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000,*,category='linear'):
        data=self.get('/v5/market/premium-index-price-kline',{'category':category,'symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_open_interest(self,symbol,start_ms,end_ms,interval='5min',limit=200,*,category='linear'):
        data=self.get('/v5/market/open-interest',{'category':category,'symbol':symbol,'intervalTime':interval,'startTime':start_ms,'endTime':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_funding(self,symbol,start_ms,end_ms,limit=200,*,category='linear'):
        data=self.get('/v5/market/funding/history',{'category':category,'symbol':symbol,'startTime':start_ms,'endTime':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_long_short_ratio(self,symbol,start_ms,end_ms,interval='5min',limit=500,*,category='linear'):
        data=self.get('/v5/market/account-ratio',{'category':category,'symbol':symbol,'period':interval,'startTime':start_ms,'endTime':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])
