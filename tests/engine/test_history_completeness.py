import pytest
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.strategies.base import StrategyDefinition,DataRequirement
from strattester.engine.executor import execute_strategy

class Count:
    def run(self,candles,checkpoint=None): return sum(1 for _ in candles)

def _definition(tf='1m'):
    return StrategyDefinition('coverage-audit','1',(DataRequirement('candles',(tf,)),),Count)

def test_bounded_backtest_rejects_internal_gap(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1),Candle('BTCUSDT','1m',120000,1,1,1,1,1)])
    with pytest.raises(RuntimeError):
        execute_strategy(_definition(),s,'BTCUSDT',start_ms=0,end_ms=120000)
    s.close()

def test_bounded_backtest_rejects_missing_boundary(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','1m',60000,1,1,1,1,1),Candle('BTCUSDT','1m',120000,1,1,1,1,1)])
    with pytest.raises(RuntimeError):
        execute_strategy(_definition(),s,'BTCUSDT',start_ms=0,end_ms=120000)
    s.close()

def test_bounded_backtest_uses_native_timeframe_step(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','5m',t,1,1,1,1,1) for t in (0,300000,600000)])
    r=execute_strategy(_definition('5m'),s,'BTCUSDT',start_ms=0,end_ms=600000)
    assert r.output==3
    s.close()
