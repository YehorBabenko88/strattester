from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.engine.executor import execute_strategy
from strattester.strategies.registry import builtin_registry

def _seed(s):
    rows=[]
    p=100.0
    for i in range(40):
        close=p+(2 if i%4<2 else -1)
        rows.append(Candle('BTCUSDT','1m',i*60_000,p,max(p,close)+1,min(p,close)-1,close,100+i*10))
        p=close
    s.upsert_candles(rows)

def test_poc_and_volatility_return_common_trade_metrics(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db'); _seed(s)
    defs={x.id:x for x in builtin_registry().discover()}
    for sid in ('poc_mean_reversion','vol_compression_expansion'):
        out=execute_strategy(defs[sid],s,'BTCUSDT',start_ms=0,end_ms=39*60_000).output
        assert 'trades' in out and 'metrics' in out
        assert out['metrics']['trades']==len(out['trades'])
    s.close()
