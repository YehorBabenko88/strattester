from strattester.marketdata.bybit_client import BybitClient
from strattester.marketdata.instruments import InstrumentRegistry,InstrumentStatus
from strattester.marketdata.universe_sync import UniverseSynchronizer
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState

class PayloadResponse:
    status_code=200
    def __init__(self,payload): self.payload=payload
    def json(self): return self.payload
class PayloadSession:
    def __init__(self,payload): self.payload=payload
    def get(self,*a,**k): return PayloadResponse(self.payload)

def test_bybit_discovers_only_trading_usdt_linear_perpetuals():
    payload={'retCode':0,'result':{'list':[
      {'symbol':'BTCUSDT','status':'Trading','quoteCoin':'USDT','contractType':'LinearPerpetual'},
      {'symbol':'OLDUSDT','status':'Settled','quoteCoin':'USDT','contractType':'LinearPerpetual'},
      {'symbol':'BTCUSDC','status':'Trading','quoteCoin':'USDC','contractType':'LinearPerpetual'}]}}
    c=BybitClient(session=PayloadSession(payload))
    assert c.fetch_linear_symbols()=={'BTCUSDT'}

def test_universe_sync_retains_disappeared_instrument(tmp_path):
    class C:
        def __init__(self): self.symbols={'AUSDT','BUSDT'}
        def fetch_linear_symbols(self): return set(self.symbols)
    c=C(); reg=InstrumentRegistry.open(tmp_path/'i.db'); u=UniverseSynchronizer(reg,c)
    u.sync(1000); c.symbols={'BUSDT'}; u.sync(2000)
    assert reg.get('AUSDT').status is InstrumentStatus.DELISTED
    assert reg.eligible_at('AUSDT',1500)
    reg.close()

def test_empty_exchange_snapshot_does_not_mass_delist(tmp_path):
    from strattester.marketdata.universe_sync import UniverseSnapshotError
    class C:
        def __init__(self): self.symbols={'AUSDT','BUSDT'}
        def fetch_linear_symbols(self): return set(self.symbols)
    c=C(); reg=InstrumentRegistry.open(tmp_path/'i.db'); u=UniverseSynchronizer(reg,c)
    u.sync(1000); c.symbols=set()
    try:
        u.sync(2000)
        assert False, 'expected suspicious snapshot rejection'
    except UniverseSnapshotError:
        pass
    assert reg.active_symbols()=={'AUSDT','BUSDT'}
    reg.close()

def test_reverse_chronological_pages_do_not_skip_middle(tmp_path):
    def row(t): return [str(t),'1','1.1','.9','1','10','100']
    class ReversePaged:
        def __init__(self): self.calls=[]
        def fetch_klines(self,symbol,start,end,interval='1',limit=1000):
            self.calls.append((start,end))
            all_rows=[row(0),row(60000),row(120000),row(180000),row(240000)]
            eligible=[r for r in all_rows if start<=int(r[0])<=end]
            return list(reversed(eligible))[:2]
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    r=SyncEngine(s,ReversePaged(),clock_ms=lambda:999999).sync_requirement(DataRequirement('BTCUSDT',start_ms=0,end_ms=240000))
    assert r.state is SyncState.READY
    assert s.coverage('BTCUSDT').count==5
    s.close()
