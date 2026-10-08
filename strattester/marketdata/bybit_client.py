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
        if self.retry.attempts<1 or self.retry.base_delay<0 or self.retry.max_delay<0:
            raise ValueError("invalid retry policy")
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
                    retry_after=None
                    try: retry_after=float(r.headers.get('Retry-After')) if r.headers.get('Retry-After') else None
                    except (TypeError,ValueError): retry_after=None
                elif r.status_code>=400: raise BybitResponseError(f'Bybit HTTP {r.status_code}')
                else:
                    data=r.json()
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
                self.sleep(min(max(exponential,hinted),self.retry.max_delay))
                retry_after=None
        raise last or RetryableBybitError('Bybit request failed')

    def fetch_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000):
        data=self.get('/v5/market/kline',{'category':'linear','symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])


    def fetch_linear_instruments(self, status=None):
        instruments = []
        cursor = None
        seen_cursors = set()

        while True:
            params = {
                'category': 'linear',
                'limit': 1000,
            }

            if status is not None:
                if not isinstance(status, str) or not status.strip():
                    raise ValueError(
                        'instrument status must be a non-empty string'
                    )
                params['status'] = status.strip()

            if cursor:
                params['cursor'] = cursor

            # If any page request fails, the exception propagates and this
            # method returns no partial universe to its caller.
            data = self.get(
                '/v5/market/instruments-info',
                params,
            )

            if not isinstance(data, dict):
                raise BybitResponseError(
                    'Bybit instruments response must be an object'
                )

            result = data.get('result')

            if not isinstance(result, dict):
                raise BybitResponseError(
                    'Bybit instruments response has invalid result'
                )

            rows = result.get('list')

            if not isinstance(rows, list):
                raise BybitResponseError(
                    'Bybit instruments response has invalid result.list'
                )

            for row in rows:
                if not isinstance(row, dict):
                    raise BybitResponseError(
                        'Bybit instruments response contains invalid row'
                    )

                row_status = row.get('status')

                if (
                    row.get('quoteCoin') == 'USDT'
                    and row.get('contractType') == 'LinearPerpetual'
                    and (
                        row_status == 'Trading'
                        if status is None
                        else row_status == status.strip()
                    )
                ):
                    instruments.append(dict(row))

            next_cursor = result.get('nextPageCursor', '')

            if next_cursor is None:
                next_cursor = ''

            if not isinstance(next_cursor, str):
                raise BybitResponseError(
                    'Bybit instruments response has invalid nextPageCursor'
                )

            if not next_cursor:
                break

            if next_cursor in seen_cursors:
                raise BybitResponseError(
                    'Bybit instruments pagination repeated cursor'
                )

            seen_cursors.add(next_cursor)
            cursor = next_cursor

        return instruments


    def fetch_linear_symbols(self):
        return {x.get('symbol') for x in self.fetch_linear_instruments() if x.get('symbol')}



    def fetch_mark_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000):
        data=self.get('/v5/market/mark-price-kline',{'category':'linear','symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_index_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000):
        data=self.get('/v5/market/index-price-kline',{'category':'linear','symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_premium_klines(self,symbol,start_ms,end_ms,interval='1',limit=1000):
        data=self.get('/v5/market/premium-index-price-kline',{'category':'linear','symbol':symbol,'interval':interval,'start':start_ms,'end':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_open_interest(self,symbol,start_ms,end_ms,interval='5min',limit=200):
        data=self.get('/v5/market/open-interest',{'category':'linear','symbol':symbol,'intervalTime':interval,'startTime':start_ms,'endTime':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_funding(self,symbol,start_ms,end_ms,limit=200):
        data=self.get('/v5/market/funding/history',{'category':'linear','symbol':symbol,'startTime':start_ms,'endTime':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])

    def fetch_long_short_ratio(self,symbol,start_ms,end_ms,interval='5min',limit=500):
        data=self.get('/v5/market/account-ratio',{'category':'linear','symbol':symbol,'period':interval,'startTime':start_ms,'endTime':end_ms,'limit':limit})
        return data.get('result',{}).get('list',[])
