from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.engine.executor import execute_strategy
from strattester.strategies.registry import builtin_registry

def test_smc_adapter_emits_trades_and_cost_aware_metrics(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    rows=[
      (0,100,101,99,100),(60_000,100,102,99,101),(120_000,101,103,100,102),
      (180_000,102,104,101,103),(240_000,103,105,102,104),(300_000,104,110,103,109),
      (360_000,109,111,108,110),(420_000,110,112,109,111),
    ]
    s.upsert_candles([Candle('BTCUSDT','1m',t,o,h,l,c,100) for t,o,h,l,c in rows])
    d={x.id:x for x in builtin_registry().discover()}['smc_control_momentum']
    out=execute_strategy(d,s,'BTCUSDT',start_ms=0,end_ms=420_000).output
    assert 'trades' in out and 'metrics' in out
    assert out['metrics']['trades']==len(out['trades'])
    if out['trades']:
        assert out['metrics']['fees']>0
        assert all(x['entry_time']>=0 for x in out['trades'])
    s.close()
