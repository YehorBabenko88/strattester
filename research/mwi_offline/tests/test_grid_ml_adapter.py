import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.grid_ml_adapter import prepare_request,AUDITED_GRID_HEAD

def request():
 return dict(schema='mwi.local.grid-ml-preparation.request.v1',observed_grid_head=AUDITED_GRID_HEAD,
  market_content_dataset_id='a'*64,feature_cohort_id='b'*64,feature_version='toy-v1',
  native_dataset_uuid=None,native_dataset_hash=None,evidence_class='SYNTHETIC',
  knowledge_cutoff_ms=3600000,sample_count=64,task='binary',model_family='mwi_research_binary_prototype',
  search_space=dict(target_key=['bounce'],objective=['binary'],n_estimators=[16],max_depth=[2],learning_rate=[.05]),
  resources=dict(threads=1,timeout_seconds=60,ram_limit_mb=512,cpu=1,ram_gb=.5,scratch_gb=.1,gpu=False))
class Checks(unittest.TestCase):
 def test_prepare_is_blocked_data_only_and_preserves_ids(self):
  q=request();before=copy.deepcopy(q);r=prepare_request(q)
  self.assertEqual(q,before);self.assertEqual(r['status'],'BLOCKED');self.assertIs(r['submit_allowed'],False)
  self.assertIs(r['training_allowed'],False);self.assertIs(r['promotion_allowed'],False)
  self.assertEqual(r['dataset']['market_content_dataset_id'],'a'*64);self.assertIsNone(r['native_arguments_if_owner_admits']['dataset_id'])
  self.assertEqual(r['combination_count'],1);self.assertIn('OWNER_INTERFACE_NOT_ACCEPTED',r['blockers'])
 def test_declared_native_mapping_does_not_grant(self):
  q=request();q.update(native_dataset_uuid='12345678-1234-4234-8234-123456789abc',native_dataset_hash='c'*64)
  r=prepare_request(q);self.assertEqual(r['dataset']['native_mapping_status'],'CALLER_DECLARED_NOT_VERIFIED');self.assertFalse(r['submit_allowed'])
 def test_product_bound_before_expansion(self):
  q=request();q['search_space']['n_estimators']=list(range(1,33));q['search_space']['max_depth']=[1,2]
  with self.assertRaisesRegex(ValueError,'SEARCH_PRODUCT_BUDGET'):prepare_request(q)
 def test_strict_scalars_ids_schema_grants(self):
  for key,value in (('sample_count',True),('knowledge_cutoff_ms',-1),('observed_grid_head','d'*40),('market_content_dataset_id','bad'),('evidence_class','HISTORICAL'),('task','multiclass'),('native_dataset_uuid','a'*64),('schema','shared'),('submit_allowed',True)):
   q=request();q[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):prepare_request(q)
 def test_no_callbacks_iterators_or_custom_numbers(self):
  class Evil(list):
   def __iter__(self):raise AssertionError('callback executed')
  for value in ((x for x in [1]),Evil([1]),lambda:1):
   q=request();q['search_space']['max_depth']=value
   with self.assertRaises(ValueError):prepare_request(q)
 def test_resource_and_hyperparameter_caps(self):
  for path,key,value in (('resources','threads',2),('resources','gpu',True),('resources','timeout_seconds',61),('resources','cpu',float('nan')),('search_space','objective',['multiclass']),('search_space','target_key',['']),('search_space','max_depth',[True]),('search_space','learning_rate',[float('inf')])):
   q=request();q[path][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):prepare_request(q)
 def test_native_pair_and_missing_fields(self):
  q=request();q['native_dataset_hash']='c'*64
  with self.assertRaises(ValueError):prepare_request(q)
  q=request();del q['feature_version']
  with self.assertRaises(ValueError):prepare_request(q)
 def test_output_is_owned_copy(self):
  q=request();r=prepare_request(q);r['native_arguments_if_owner_admits']['search_space']['max_depth'][0]=3
  self.assertEqual(q['search_space']['max_depth'],[2])
 def test_custom_schema_evidence_and_huge_integer_refused(self):
  class String(str):
   def __eq__(self,other):raise AssertionError('custom equality executed')
  for key,value in (('schema',String('mwi.local.grid-ml-preparation.request.v1')),('evidence_class',String('SYNTHETIC')),('sample_count',10**1000)):
   q=request();q[key]=value
   with self.assertRaises(ValueError):prepare_request(q)
if __name__=='__main__':unittest.main(verbosity=2)
