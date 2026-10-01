from strattester.marketdata.bybit_client import BybitClient

class R:
    status_code=200
    def json(self): return {'retCode':0,'result':{'list':[['1','2']]}}
class S:
    def __init__(self): self.calls=[]
    def get(self,url,params=None,timeout=None):
        self.calls.append((url,params)); return R()

def test_rich_history_methods_use_explicit_bybit_endpoints():
    s=S(); c=BybitClient(session=s)
    c.fetch_mark_klines('BTCUSDT',0,60_000,'1')
    c.fetch_index_klines('BTCUSDT',0,60_000,'1')
    c.fetch_premium_klines('BTCUSDT',0,60_000,'1')
    c.fetch_open_interest('BTCUSDT',0,60_000,'5min')
    c.fetch_funding('BTCUSDT',0,60_000)
    c.fetch_long_short_ratio('BTCUSDT',0,60_000,'5min')
    paths=[u.split('api.bybit.com')[-1] for u,_ in s.calls]
    assert paths==[
      '/v5/market/mark-price-kline','/v5/market/index-price-kline','/v5/market/premium-index-price-kline',
      '/v5/market/open-interest','/v5/market/funding/history','/v5/market/account-ratio']
