from strattester.research.runner import ResearchRunner
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.strategies.base import StrategyDefinition,DataRequirement

class NeedsMark:
    def run_context(self,context,checkpoint=None):
        return (context.coverage('candles','1m').count,context.coverage('mark_price','1m').count)

def test_runner_repairs_missing_required_history_before_backtest(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    class C:
        calls=[]
        def fetch_klines(self,symbol,start,end,interval='1'):
            self.calls.append(('candles',start,end))
            return [['60000','100','101','99','100','1','100'],['0','100','101','99','100','1','100']]
        def fetch_mark_klines(self,symbol,start,end,interval='1'):
            self.calls.append(('mark',start,end))
            return [['60000','100','101','99','100'],['0','100','101','99','100']]
    d=StrategyDefinition('needs-mark','1',(
      DataRequirement('candles',('1m',)),
      DataRequirement('mark_price',('1m',)),
    ),NeedsMark)
    client=C()
    runner=ResearchRunner(s,client,clock_ms=lambda:999_999)
    result=runner.run(d,{'symbol':'BTCUSDT','launchTime':'0'},start_ms=0,end_ms=60_000)
    assert result.output==(2,2)
    first_calls=len(client.calls)
    result2=runner.run(d,{'symbol':'BTCUSDT','launchTime':'0'},start_ms=0,end_ms=60_000)
    assert result2.output==(2,2)
    assert len(client.calls)==first_calls
    s.close()
