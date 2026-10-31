import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
GRID=Path(os.environ.get('GRID_REFERENCE',ROOT.parent/'grid'))
MATH=Path(os.environ.get('MATH_REFERENCE',ROOT.parent/'math'))
if not (GRID/'tests/test_history_export.py').is_file() or not (MATH/'python/history_worker.py').is_file():
    if os.environ.get('HISTORY_REQUIRE_CROSSREPO')=='1':
        raise RuntimeError('required immutable cross-repository references are missing')
    raise unittest.SkipTest('cross-repository fixture refs are required; history-integration CI provisions exact pins')
sys.path.insert(0,str(GRID))
spec=importlib.util.spec_from_file_location('fixture',GRID/'tests/test_history_export.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from grid.history_export import export_records
from strattester.research.grid_math_history import MathClient, replay, digest, runtime_pin

def git(*args):return subprocess.check_output(['git','-C',str(MATH),*args],text=True).strip()
def client(**kw):return MathClient(MATH,git('rev-parse','HEAD'),git('rev-parse','HEAD^{tree}'),runtime_pin(),**kw)
def dataset(n=80):
    r,q,t=fixture.fixture(n);return export_records(r,q,t)
def policy():
    return {'train_end_ms':30*60000,'validation_end_ms':50*60000,'test_end_ms':80*60000,
       'fee_bps':5.,'slippage_bps':2.,'funding_policy':'EXPLICIT_PERPETUAL','funding':[
            {'timestamp_ms':i*60000,'rate':.0001,'mark_price':100.} for i in range(80)],
       'notional':100.,'latency_ms':0,'starting_cash':10000.}

class Integration(unittest.TestCase):
    def test_nonzero_latency_uses_next_executable_bar(self):
        class Long:
            commit='fixture';tree='fixture';manifest={};python_sha256='fixture'
            def predict(s,prices,fp,train_count=None):return {'forecast':prices[-1]+1,'volatility':0.}
        d=dataset();r=replay(d,d['dataset_fingerprint'],Long(),{**policy(),'latency_ms':1})
        self.assertTrue(r['fills'])
        for fill in r['fills']:self.assertGreaterEqual(fill['entry_ms'],fill['decision_ms']+1)
        self.assertTrue(all(a['exit_ms']<=b['entry_ms'] for a,b in zip(r['fills'],r['fills'][1:])))

    def test_funding_event_count_bound_before_allocation(self):
        with patch('strattester.research.grid_math_history.range',create=True,side_effect=AssertionError('must not allocate')):
            with self.assertRaises(ValueError):
                replay(dataset(),dataset()['dataset_fingerprint'],None,{**policy(),'funding_interval_ms':1})

    def test_spot_cannot_short_without_inventory(self):
        class Short:
            commit='fixture';tree='fixture';manifest={};python_sha256='fixture'
            def predict(s,prices,fp,train_count=None):return {'forecast':prices[-1]-1,'volatility':0.}
        d=dataset();d['request']['market_type']='spot'
        d['dataset_fingerprint']=digest({k:v for k,v in d.items() if k!='dataset_fingerprint'})
        r=replay(d,d['dataset_fingerprint'],Short(),{**policy(),'funding_policy':'NOT_APPLICABLE_SPOT','funding':[]})
        self.assertEqual(r['fills'],[])

    def test_insufficient_cash_rejects_entry(self):
        class Long:
            commit='fixture';tree='fixture';manifest={};python_sha256='fixture'
            def predict(s,prices,fp,train_count=None):return {'forecast':prices[-1]+1,'volatility':0.}
        d=dataset()
        r=replay(d,d['dataset_fingerprint'],Long(),{**policy(),'starting_cash':50.})
        self.assertEqual(r['fills'],[])

    def test_validation_selection_uses_carried_cash(self):
        class Long:
            commit='fixture';tree='fixture';manifest={};python_sha256='fixture'
            def predict(s,prices,fp,train_count=None):return {'forecast':prices[-1]+1,'volatility':0.}
        d=dataset()
        for row in d['rows'][:30]:row['close']=row['open']-1
        d['dataset_fingerprint']=digest({k:v for k,v in d.items() if k!='dataset_fingerprint'})
        r=replay(d,d['dataset_fingerprint'],Long(),{**policy(),'starting_cash':101.})
        self.assertEqual(r['splits']['validation']['trades'],0)
        self.assertEqual(r['selected_model'],'FLAT')

    def test_zero_return_and_costs_and_funding_sign(self):
        class Fixed:
            commit='fixture';tree='fixture';manifest={};python_sha256='fixture'
            def __init__(s,side):s.side=side
            def predict(s,prices,fp,train_count=None):return {'forecast':prices[-1]+s.side,'volatility':0.}
        d=dataset()
        for bar in d['rows']:
            for k in ('open','high','low','close'):bar[k]=100.
        d['dataset_fingerprint']=digest({k:v for k,v in d.items() if k!='dataset_fingerprint'})
        for side in (1,-1):
            result=replay(d,d['dataset_fingerprint'],Fixed(side),policy())
            self.assertEqual(result['metrics']['gross_pnl'],0.)
            self.assertGreater(result['metrics']['fees'],0.)
            self.assertGreater(result['metrics']['slippage'],0.)
            self.assertEqual(result['metrics']['funding']>0,side>0)
        flat=replay(d,d['dataset_fingerprint'],Fixed(0),policy())
        self.assertEqual(flat['fills'],[])
        self.assertEqual(flat['metrics']['net_pnl'],0.)

    def test_missing_funding_and_delayed_features(self):
        d=dataset()
        with client() as c:
            with self.assertRaises(ValueError):replay(d,d['dataset_fingerprint'],c,{**policy(),'funding':[]})
            with self.assertRaises(ValueError):replay(d,d['dataset_fingerprint'],c,{**policy(),'funding':policy()['funding'][1:]})
            # No row has become knowable by its immediate next-bar entry.
            for row in d['rows']:row['available_at_ms']=d['request']['end_ms']
            d['dataset_fingerprint']=digest({k:v for k,v in d.items() if k!='dataset_fingerprint'})
            with self.assertRaises(ValueError):replay(d,d['dataset_fingerprint'],c,policy())

    def test_end_to_end_and_determinism(self):
        d=dataset();p=policy();p.update(funding_policy='EXPLICIT_PERPETUAL',funding=[
            {'timestamp_ms':i*60000,'rate':.0001,'mark_price':100.} for i in range(81)])
        with client() as c:
            a=replay(d,d['dataset_fingerprint'],c,p)
            self.assertEqual(a,replay(d,d['dataset_fingerprint'],c,p))
        self.assertEqual(a['schema'],'strattester.terminan.result.v1')
        self.assertFalse(a['training_authorized']);self.assertFalse(a['trading_authorized'])
        self.assertEqual(a['training_candidate'],'BLOCKED_SYNTHETIC')
        self.assertTrue(a['fills']);self.assertEqual(set(a['splits']),{'train','validation','test'})
        self.assertTrue(all(x['decision_ms']<=x['entry_ms'] for x in a['fills']))
        self.assertAlmostEqual(a['metrics']['net_pnl'],a['metrics']['gross_pnl']-a['metrics']['fees']-a['metrics']['slippage']-a['metrics']['funding'])
        if os.environ.get('HISTORY_EVIDENCE_ROOT'):
            out=Path(os.environ['HISTORY_EVIDENCE_ROOT']);out.mkdir(parents=True,exist_ok=True)
            (out/'synthetic-replay.json').write_text(json.dumps(a,indent=2,sort_keys=True))

    def test_failure_controls(self):
        d=dataset()
        with client() as c:
            for change in (lambda x:x['rows'][0].update(close=999),lambda x:x.update(schema='future'),
                           lambda x:x['request']['units'].update(price='USD/BTC')):
                z=copy.deepcopy(d);change(z)
                with self.assertRaises(ValueError):replay(z,d['dataset_fingerprint'],c,policy())
            with self.assertRaises(ValueError):replay(d,'0'*64,c,policy())
            for p in ({**policy(),'funding_policy':'UNKNOWN'}, {**policy(),'fee_bps':float('nan')},
                      {**policy(),'validation_end_ms':20*60000}):
                with self.assertRaises(ValueError):replay(d,d['dataset_fingerprint'],c,p)

    def test_runtime_and_version_substitution(self):
        for pin in ('0'*64,):
            with self.assertRaises(ValueError):
                with MathClient(MATH,git('rev-parse','HEAD'),git('rev-parse','HEAD^{tree}'),pin):pass
        with self.assertRaises(ValueError):
            with MathClient(MATH,'0'*40,git('rev-parse','HEAD^{tree}'),runtime_pin()):pass
        with client(timeout=.000001) as c:
            with self.assertRaises(ValueError):c.predict([100.]*30,'a'*64)

    def test_future_mutation_no_earlier_effect(self):
        a=dataset();b=copy.deepcopy(a)
        for row in b['rows'][60:]:
            for k in ('open','high','low','close'):row[k]*=1.5
        b['dataset_fingerprint']=digest({k:v for k,v in b.items() if k!='dataset_fingerprint'})
        with client() as c:
            x=replay(a,a['dataset_fingerprint'],c,policy())
            y=replay(b,b['dataset_fingerprint'],c,policy())
        self.assertEqual(x['selected_model'],y['selected_model'])
        self.assertEqual([v for v in x['fills'] if v['exit_ms']<60*60000],
                         [v for v in y['fills'] if v['exit_ms']<60*60000])

if __name__=='__main__':unittest.main()
