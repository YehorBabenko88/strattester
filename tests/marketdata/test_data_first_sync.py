import pytest
from strattester.marketdata.bybit_client import BybitClient,BybitResponseError
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState

def test_full_universe_pagination_keeps_non_btc_metadata():
    client=BybitClient()
    pages=[{'result':{'category':'linear','list':[{'symbol':'ABCUSDT','launchTime':'120000'}],'nextPageCursor':'next'}},
           {'result':{'category':'linear','list':[{'symbol':'NEWUSDC','launchTime':'180000'}],'nextPageCursor':''}}]
    calls=[]
    def get(path,params):calls.append(params);return pages.pop(0)
    client.get=get
    assert [r['symbol'] for r in client.fetch_instruments()]==['ABCUSDT','NEWUSDC']
    assert calls[1]['cursor']=='next'

def test_repeating_cursor_is_not_full_discovery():
    client=BybitClient();number=[0]
    def get(*args):
        number[0]+=1
        return {'result':{'list':[{'symbol':'X'+str(number[0])}],'nextPageCursor':'again'}}
    client.get=get
    with pytest.raises(BybitResponseError,match='cursor'):client.fetch_instruments()

@pytest.mark.parametrize('existing,window',[(600000,(0,60000)),(0,(600000,660000))])
def test_ranges_never_escape_requirement(tmp_path,existing,window):
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    try:
        store.upsert_candles([Candle('X','1m',existing,1,1,1,1,1)])
        engine=SyncEngine(store,object())
        assert engine._ranges(DataRequirement('X','candles','1m',*window))==[window]
    finally:store.close()

def test_page_budget_and_cancel_preserve_progress(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'m.db');calls=[];checkpoints=[]
    class Client:
        def fetch_klines(self,symbol,start,end,interval):
            calls.append(end)
            return [[str(end),'1','1','1','1','1','1']]
    try:
        req=DataRequirement('X','candles','1m',0,120000)
        engine=SyncEngine(store,Client(),clock_ms=lambda:180000,max_pages=1,checkpoint=checkpoints.append)
        assert engine.sync_requirement(req).state is SyncState.PARTIAL
        assert len(calls)==len(checkpoints)==1
        assert engine.sync_requirement(req).state is SyncState.PARTIAL
        assert calls==[120000,60000]
        engine.cancel=lambda:True
        assert engine.sync_requirement(req).message=='cancelled'
        assert calls==[120000,60000]
    finally:store.close()

def test_response_body_budget_closes_stream_without_parsing():
    class Stream:
        status_code=200;headers={};closed=False
        def iter_content(self,chunk_size):yield b'x'*33
        def close(self):self.closed=True
    response=Stream()
    class Session:
        def get(self,*a,**kw):return response
    client=BybitClient(session=Session(),max_response_bytes=32)
    with pytest.raises(BybitResponseError,match='byte budget'):client.get('/v5/market/kline')
    assert response.closed

def test_retry_backoff_checks_cancel_without_new_request():
    flag=[False];calls=[]
    class Response:
        status_code=429;headers={}
    class Session:
        def get(self,*a,**k):calls.append(1);return Response()
    client=BybitClient(session=Session(),before_request=lambda:None,cancel=lambda:flag[0],
                       sleep=lambda _:flag.__setitem__(0,True))
    with pytest.raises(InterruptedError):client.get('/v5/market/kline')
    assert len(calls)==1
