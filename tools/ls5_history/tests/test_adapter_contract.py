import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_adapter_contract import assess_contract,EXPOSED_STAGE_E_NS
class Tests(unittest.TestCase):
 def request(self):return dict(source_sha256='a'*64,checkpoint_sha256='b'*64,category='linear',time_unit='ns',train=[0,10],validation=[12,20],test=[22,30],purge_ns=0,embargo_ns=2,samples=[],funding_status='MISSING',slippage_status='MISSING',historical_revisions='UNKNOWN',historical_availability='UNKNOWN')
 def test_missing_costs_never_qualified(self):
  r=assess_contract(self.request());self.assertEqual(r['status'],'CONTRACT_ONLY_REAL_OOS_BLOCKED');self.assertTrue(r['blockers'])
 def test_future_availability_and_exposed_interval(self):
  request=self.request();request['samples']=[dict(partition='train',origin_ns=5,feature_end_ns=4,label_end_ns=8,available_at_ns=6)]
  self.assertIn('FUTURE_OR_OVERLAPPING_LABEL_AVAILABILITY',assess_contract(request)['blockers'])
  request=self.request();request['test']=list(EXPOSED_STAGE_E_NS)
  self.assertIn('EXPOSED_STAGE_E_NOT_NEW_OOS',assess_contract(request)['blockers'])
 def test_units_and_embargo_fail_closed(self):
  for override in [dict(time_unit='ms'),dict(test=[19,30]),dict(source_sha256='bad')]:
   with self.assertRaises(ValueError):assess_contract(dict(self.request(),**override))
