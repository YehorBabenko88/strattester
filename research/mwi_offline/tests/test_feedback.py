from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mwi_offline.synthetic import generate
from mwi_offline.feedback import run_cycle, development_fit
from test_simulation_adapter import Signal, Policy


def fake_binding():
    def call(signal,bars,policy,metadata):
        return SimpleNamespace(net_pnl=-.2,gross_pnl=-.1,fees=.1,entry_time=bars[0]['t'],exit_time=bars[-1]['t'],entry_price=100.,exit_price=99.9,side=signal.side,exit_reason='EOD',metadata=metadata)
    return {'Signal':Signal,'ExecutionPolicy':Policy,'simulate_trade':call,'source_sha256':'test-double','scope':'TEST_DOUBLE_NOT_NATIVE'}


class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bars=generate(n=4200)
    def test_development_models_do_not_consume_original_final_oos(self):
        x=development_fit(self.bars)
        self.assertLess(x['development_end'],x['reserved_original_oos_start'])
        self.assertTrue(all(r['cutoff']<x['development_end'] for r in x['examples']))
    def test_immutable_results_resume_and_negative_preservation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'cycle'
            a=run_cycle(root,self.bars,fake_binding(),'a'*40)
            before={p.name:p.read_bytes() for p in (root/'artifacts').iterdir()}
            b=run_cycle(root,self.bars,fake_binding(),'a'*40,resume=True)
            self.assertEqual(a,b)
            self.assertEqual(before,{p.name:p.read_bytes() for p in (root/'artifacts').iterdir()})
            self.assertLessEqual(a['evaluated_candidates'],6);self.assertFalse(a['promotion_allowed'])
            self.assertTrue(any(c['base']['net_pnl']<0 for c in a['candidates']))
    def test_tamper_and_wrong_source_resume_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'cycle';run_cycle(root,self.bars,fake_binding(),'a'*40)
            with self.assertRaises(ValueError):run_cycle(root,self.bars,fake_binding(),'b'*40,resume=True)
            f=next((root/'artifacts').iterdir());f.write_bytes(b'{}')
            with self.assertRaises(ValueError):run_cycle(root,self.bars,fake_binding(),'a'*40,resume=True)
    def test_interruption_retained_and_resume_completes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'cycle';binding=fake_binding()
            def fail(*args,**kwargs):raise RuntimeError('synthetic interruption')
            binding['simulate_trade']=fail
            with self.assertRaises(RuntimeError):run_cycle(root,self.bars,binding,'a'*40)
            self.assertTrue(list((root/'artifacts').glob('failure-*.json')))
            result=run_cycle(root,self.bars,fake_binding(),'a'*40,resume=True)
            self.assertEqual(result['status'],'SYNTHETIC_FINITE_FEEDBACK_COMPLETE')
            self.assertTrue(list((root/'artifacts').glob('failure-*.json')))
    def test_full_future_raw_mutation_does_not_change_development_fit(self):
        import copy
        before=development_fit(self.bars);mutated=copy.deepcopy(self.bars)
        cutoff=before['reserved_original_oos_start']
        for b in mutated:
            if b['open_ms']>=cutoff:b['high']=1000.;b['low']=1.
        after=development_fit(mutated)
        self.assertEqual(before['models'],after['models'])
        self.assertEqual(before['train_ids_sha256'],after['train_ids_sha256'])
    def test_removed_result_pin_cannot_bypass_resume(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'cycle';run_cycle(root,self.bars,fake_binding(),'a'*40)
            cp=json.loads((root/'checkpoint.json').read_text());cp['artifacts'].pop('result.json')
            (root/'checkpoint.json').write_text(json.dumps(cp))
            (root/'artifacts/result.json').write_text('{}')
            with self.assertRaises(ValueError):run_cycle(root,self.bars,fake_binding(),'a'*40,resume=True)
    def test_atomic_checkpoint_publication_preserves_previous_on_replace_failure(self):
        from unittest.mock import patch
        from mwi_offline.feedback import publish_checkpoint
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);publish_checkpoint(root,{'stage':1});before=(root/'checkpoint.json').read_bytes()
            with patch('mwi_offline.feedback.os.replace',side_effect=OSError('injected publication fault')):
                with self.assertRaises(OSError):publish_checkpoint(root,{'stage':2})
            self.assertEqual(before,(root/'checkpoint.json').read_bytes())
    def test_interrupted_multifile_save_refuses_orphan_instead_of_adopting(self):
        from unittest.mock import patch
        from mwi_offline.feedback import publish_checkpoint
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'cycle';calls=[]
            def fault(where,value):
                calls.append(1)
                if len(calls)==3:raise OSError('injected multi-file publication interruption')
                publish_checkpoint(where,value)
            with patch('mwi_offline.feedback.publish_checkpoint',side_effect=fault):
                with self.assertRaises(OSError):run_cycle(root,self.bars,fake_binding(),'a'*40)
            self.assertTrue((root/'checkpoint.json').is_file())
            with self.assertRaisesRegex(ValueError,'CLOSED_INVENTORY'):run_cycle(root,self.bars,fake_binding(),'a'*40,resume=True)
    def test_frozen_policy_evaluated_on_new_synthetic_realization(self):
        with tempfile.TemporaryDirectory() as d:
            result=run_cycle(Path(d)/'cycle',self.bars,fake_binding(),'a'*40)
            self.assertIn('selected_strategy_id',result)
            self.assertEqual(result['policy_holdout']['selection_used_holdout'],False)
            self.assertEqual(result['policy_holdout']['seed'],20261113)
            self.assertGreater(result['policy_holdout']['start_ms'],max(b['end_ms'] for b in self.bars))
            self.assertNotEqual(result['policy_holdout']['dataset_id'],result['config']['dataset_id'])

if __name__=='__main__':unittest.main(verbosity=2)
