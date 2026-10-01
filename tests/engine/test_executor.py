import pytest
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.strategies.base import StrategyDefinition,DataRequirement
from strattester.engine.executor import execute_strategy
class Count:
    def run(self,candles,checkpoint=None): return sum(1 for _ in candles)
def definition(): return StrategyDefinition('count','1',(DataRequirement('candles',('1m',)),),Count)
def test_requirements_block_empty_history(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    with pytest.raises(RuntimeError): execute_strategy(definition(),s,'BTCUSDT')
    s.close()
def test_executor_streams_candles(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','1m',i*60000,1,1,1,1,1) for i in range(3)])
    r=execute_strategy(definition(),s,'BTCUSDT')
    assert r.output==3 and r.strategy_version=='1'
    s.close()
