from strattester.research_cli import main
from strattester.strategies.base import StrategyDefinition,DataRequirement
from strattester.strategies.registry import StrategyRegistry
from strattester.persistence.result_store import ResultStore

class Demo:
    def run_context(self,context,checkpoint=None):
        return {'bars':context.coverage('candles','1m').count}

class Client:
    def fetch_klines(self,symbol,start,end,interval='1'):
        return [[str(end),'1','1','1','1','1','1'],[str(start),'1','1','1','1','1','1']]

def test_research_cli_runs_and_persists_result(tmp_path,capsys):
    reg=StrategyRegistry()
    reg.register(StrategyDefinition('demo','1',(DataRequirement('candles',('1m',)),),Demo))
    db=tmp_path/'market.db'; out=tmp_path/'results.db'
    assert main(['--db',str(db),'--results-db',str(out),'--symbol','BTCUSDT','--start-ms','0','--end-ms','60000','--strategy','demo'],registry=reg,client=Client())==0
    payload=__import__('json').loads(capsys.readouterr().out)
    assert payload['results'][0]['strategy_id']=='demo'
    s=ResultStore.open(out)
    row=s.latest('BTCUSDT','demo')
    assert row is not None and row['metrics']['output']=={'bars':2}
    s.close()
