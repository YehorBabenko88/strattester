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

class RichCount:
    def run_context(self,context,checkpoint=None):
        return {
            'candles':sum(1 for _ in context.candles('1m')),
            'mark_rows':context.coverage('mark_price','1m').count,
        }

def test_executor_accepts_ready_rich_requirements_and_context(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','1m',0,100,101,99,100,1,100,True)])
    s.upsert_price_klines('mark_price','BTCUSDT',[['0','100','101','99','100']],'1m')
    d=StrategyDefinition('rich','1',(
        DataRequirement('candles',('1m',)),
        DataRequirement('mark_price',('1m',)),
    ),RichCount)
    r=execute_strategy(d,s,'BTCUSDT')
    assert r.output=={'candles':1,'mark_rows':1}
    s.close()

def test_executor_respects_requested_time_range(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','1m',i*60000,1,1,1,1,1) for i in range(5)])
    r=execute_strategy(definition(),s,'BTCUSDT',start_ms=60000,end_ms=180000)
    assert r.output==3
    s.close()
