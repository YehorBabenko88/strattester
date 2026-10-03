from types import SimpleNamespace
from strattester.research.result_persistence import persist_report

class Store:
    def __init__(self): self.args=None
    def put(self,*args,**kwargs): self.args=(args,kwargs)

def test_persist_report_serializes_core_metrics():
    result=SimpleNamespace(strategy_id='A',strategy_version='1',fingerprint='fp')
    report=SimpleNamespace(primary=SimpleNamespace(trades=2,net_pnl=3.0,fees=.2,win_rate=.5,profit_factor=2.0,max_drawdown=1.0,expectancy=1.5))
    s=Store()
    persist_report(s,'run-1','BTCUSDT',result,report)
    args,_=s.args
    assert args[:4]==('run-1','BTCUSDT','A','1')
    assert args[4]['trades']==2 and args[4]['fingerprint']=='fp'
