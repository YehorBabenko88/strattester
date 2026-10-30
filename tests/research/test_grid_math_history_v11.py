import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
GRID=Path(os.environ.get('GRID_REFERENCE',ROOT.parent/'grid'))
MATH=Path(os.environ.get('MATH_REFERENCE',ROOT.parent/'math'))
if not (GRID/'grid/history_export_v11.py').is_file() or not (MATH/'python/history_timed_worker.py').is_file():
    if os.environ.get('HISTORY_REQUIRE_CROSSREPO')=='1':raise RuntimeError('v1.1 producer pins required')
    raise unittest.SkipTest('v1.1 producer refs not provisioned')
sys.path.insert(0,str(GRID))
spec=importlib.util.spec_from_file_location('fixture_v11',GRID/'tests/test_history_export.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from grid.history_export_v11 import export_records_v11, dataset_content
from strattester.research.grid_math_history import admit, MathClient, replay, digest, runtime_pin

def dataset():
    r,q,t=fixture.fixture();return export_records_v11(r,q,t)
def policy():
    return {'train_end_ms':30*60000,'validation_end_ms':50*60000,'test_end_ms':80*60000,
      'fee_bps':5.,'slippage_bps':2.,'notional':100.,'starting_cash':10000.,'latency_ms':0,
      'funding_policy':'EXPLICIT_PERPETUAL','funding_interval_ms':60000,'funding_anchor_ms':0,
      'funding':[{'timestamp_ms':i*60000,'rate':.0001,'mark_price':100.} for i in range(80)],
      'model_version':'grid-frozen-analog-v1'}
def client(**kw):
    def git(*a):return subprocess.check_output(['git','-C',str(MATH),*a],text=True).strip()
    return MathClient(MATH,git('rev-parse','HEAD'),git('rev-parse','HEAD^{tree}'),runtime_pin(),timed=True,**kw)


class TimedIntegration(unittest.TestCase):
    def test_delayed_publication_does_not_reuse_known_horizon_labels(self):
        from strattester.research.history_terminan import review_packet
        d=dataset();d['rows'][55]['available_at_ms']+=60000
        d['dataset_id']=digest(dataset_content(d))
        d['dataset_fingerprint']=digest({k:v for k,v in d.items() if k!='dataset_fingerprint'})
        with client() as c:r=replay(d,d['dataset_fingerprint'],c,policy())
        packet=review_packet(r,r['completion_receipt'])
        self.assertTrue(packet['trade_events'])
        self.assertTrue(all(x['origin_ms']<x['label_event_end_ms'] for x in r['training_candidates']))

    def test_end_to_end_times_receipts_and_oos(self):
        d=dataset()
        with client() as c:
            r=replay(d,d['dataset_fingerprint'],c,policy())
        self.assertEqual(r['schema'],'strattester.terminan.result.v1.1')
        self.assertEqual(r['dataset_id'],d['dataset_id'])
        self.assertEqual(r['watermark_ms'],d['watermark_ms'])
        self.assertTrue(r['math_trace'])
        for x in r['math_trace']:
            self.assertLessEqual(x['watermark_ms'],x['feature_available_at_ms'])
            self.assertLessEqual(x['feature_available_at_ms'],x['decision_ms'])
        for x in r['training_candidates']:
            self.assertLess(x['origin_ms'],x['label_event_end_ms'])
            self.assertLessEqual(x['label_event_end_ms'],x['label_available_at_ms'])
            self.assertFalse(x['eligible_for_training'])
        self.assertFalse(r['execution_authority'])
        if os.environ.get('HISTORY_EVIDENCE_ROOT'):
            out=Path(os.environ['HISTORY_EVIDENCE_ROOT']);out.mkdir(parents=True,exist_ok=True)
            (out/'timed-synthetic-replay.json').write_text(json.dumps(r,indent=2,sort_keys=True))

    def test_rehashed_invalid_dataset_id_and_watermark_denied(self):
        for mutate in (lambda d:d['rows'][0].update(watermark_ms=120000),
                       lambda d:d.update(dataset_id='0'*64),lambda d:d.update(watermark_ms=0),
                       lambda d:d['source'].update(source_revision='bad')):
            d=dataset();mutate(d);d['dataset_fingerprint']=digest({k:v for k,v in d.items() if k!='dataset_fingerprint'})
            with self.assertRaises(ValueError):admit(d,d['dataset_fingerprint'])

    def test_model_and_service_failure_never_yield_result(self):
        d=dataset()
        with client() as c:
            with self.assertRaises(ValueError):replay(d,d['dataset_fingerprint'],c,{**policy(),'model_version':'forged'})
        with client(timeout=.000001) as c:
            with self.assertRaises(ValueError):replay(d,d['dataset_fingerprint'],c,policy())

if __name__=='__main__':unittest.main()
