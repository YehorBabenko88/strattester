from dataclasses import dataclass
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.strategy import candidates
from mwi_offline.simulation_adapter import simulate_candidate, inspect_binding

@dataclass
class Signal:
    decision_time:int;side:str;entry_kind:str;entry_price:object;stop_loss:float;take_profit:float
@dataclass
class Policy:
    bar_ms:int;fee_rate:float;slippage_bps:float;ambiguous_policy:str;position_usd:float

class Checks(unittest.TestCase):
    def setUp(self):
        self.c=candidates('a'*64,'b'*64)[2]
        self.e={'id':'TOYUSDT:60000','cutoff':60000,'label_end':780000,'baseline':[1,0,0,0,.001,1,1,1]}
        self.bars=[dict(symbol='TOYUSDT',open_ms=i*60000,end_ms=(i+1)*60000,available_ms=(i+1)*60000,open=100.,high=100.1,low=99.9,close=100.,volume=1.) for i in range(13)]
        self.calls=[]
        def call(signal,bars,policy,metadata):
            self.calls.append((signal,bars,policy));return SimpleNamespace(net_pnl=-.2,gross_pnl=-.1,fees=.1,entry_time=bars[0]['t'],exit_time=bars[-1]['t'],entry_price=100.,exit_price=99.9,side=signal.side,exit_reason='EOD',metadata=metadata)
        self.binding={'Signal':Signal,'ExecutionPolicy':Policy,'simulate_trade':call,'source_sha256':'test-double','scope':'TEST_DOUBLE_NOT_NATIVE'}
    def test_calls_existing_interface_with_explicit_costs_and_latency(self):
        r=simulate_candidate(self.c,self.e,[.9,.05,.05],self.bars,self.binding)
        self.assertEqual(r['status'],'SIMULATED');s,rows,p=self.calls[0]
        self.assertGreaterEqual(rows[0]['t'],self.e['cutoff']+60000)
        self.assertEqual(p.ambiguous_policy,'SL_FIRST');self.assertEqual(p.slippage_bps,2.)
    def test_missing_future_bar_refuses(self):
        r=simulate_candidate(self.c,self.e,[.9,.05,.05],self.bars[:3]+self.bars[4:],self.binding)
        self.assertEqual(r['status'],'REFUSED');self.assertEqual(self.calls,[])
    def test_risk_and_capital_cannot_be_overridden(self):
        e=dict(self.e);e['baseline']=[1,0,0,0,1.,1,1,1]
        self.assertEqual(simulate_candidate(self.c,e,[.9,.05,.05],self.bars,self.binding)['status'],'REFUSED')
        self.assertEqual(simulate_candidate(self.c,self.e,[.9,.05,.05],self.bars,self.binding,capital=10)['status'],'REFUSED')
    def test_wait_never_calls_simulator(self):
        self.assertEqual(simulate_candidate(self.c,self.e,[.1,.1,.8],self.bars,self.binding)['status'],'WAIT')
        self.assertEqual(self.calls,[])
    def test_unknown_instrument_and_nonfinite_capital_refused(self):
        e=dict(self.e);e['id']='OTHER:60000'
        self.assertEqual(simulate_candidate(self.c,e,[.9,.05,.05],self.bars,self.binding)['status'],'REFUSED')
        for capital in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):simulate_candidate(self.c,self.e,[.9,.05,.05],self.bars,self.binding,capital=capital)
    def test_window_is_bounded_before_allocation(self):
        for value in (True,-1,10**20):
            e=dict(self.e);e['label_end']=value
            with self.assertRaises(ValueError):simulate_candidate(self.c,e,[.9,.05,.05],self.bars,self.binding)
    def test_source_binding_inspection_is_read_only(self):
        root=Path(__file__).resolve().parents[3]
        import hashlib
        expected='99c1a3a7907b0481c0f2a4f239fb6808f137834b39fffaf7885ef60f66246832'
        if hashlib.sha256((root/'strattester/research/execution.py').read_bytes()).hexdigest()!=expected:
            with self.assertRaisesRegex(ValueError,'RAW_SOURCE_PIN'):inspect_binding(root)
        else:self.assertEqual(inspect_binding(root)['execution_sha256'],expected)
        self.assertNotIn('strattester.research.execution',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
