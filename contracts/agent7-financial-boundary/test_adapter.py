import copy,hashlib,importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parent

def load():
 spec=importlib.util.spec_from_file_location('financial_boundary_adapter',ROOT/'adapter.py')
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def digest(profile):
 return hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()

class BoundaryTests(unittest.TestCase):
 def setUp(self):
  self.m=load()
  self.profile={'schema':'agent7.financial-unit-profile.v2','profile_id':'FIXTURE_ONLY_NOT_PROVIDER','currency':'TEST','unit':'TEST_CURRENCY','decimal_places':2,'max_digits':40}
  self.pin=digest(self.profile)
  self.record={'schema':'agent7.financial-input.v2','raw_pnl':'10.00','fees':'1.00','slippage':'0.50','funding':'0.25','currency':'TEST','unit':'TEST_CURRENCY','profile_sha256':self.pin,'calculation_basis':'GROSS_MINUS_SIGNED_COSTS','provenance':{'source_head':'a'*40,'source_tree':'b'*40,'input_manifest_sha256':'c'*64,'strategy_id':'synthetic','strategy_version':'1','fidelity':'PAPER_FIXTURE','mode':'HISTORICAL'}}
 def run_record(self,record=None,profile=None,admitted=None):
  return self.m.convert(self.record if record is None else record,self.profile if profile is None else profile,{self.pin} if admitted is None else admitted)
 def test_gross_costs_once(self):
  result=self.run_record();self.assertEqual(result['gross_pnl'],'10.00');self.assertEqual(result['net_pnl'],'8.25')
 def test_already_net_no_double_cost(self):
  self.record.update(raw_pnl='8.25',calculation_basis='NET_INCLUDES_SIGNED_COSTS');r=self.run_record();self.assertEqual(r['net_pnl'],'8.25');self.assertEqual(r['gross_pnl'],'10.00')
 def test_negative_funding_is_credit(self):
  self.record['funding']='-0.25';self.assertEqual(self.run_record()['net_pnl'],'8.75')
 def test_unqualified_profile_refused(self):
  with self.assertRaises(ValueError):self.run_record(admitted=set())
 def test_profile_digest_mismatch(self):
  self.profile['decimal_places']=3
  with self.assertRaises(ValueError):self.run_record()
 def test_missing_currency_or_units(self):
  for key in ['currency','unit']:
   record=copy.deepcopy(self.record);del record[key]
   with self.assertRaises(ValueError):self.run_record(record)
 def test_float_and_nonfinite_refused(self):
  for value in [10.0,float('nan'),'NaN','Infinity','1e2','-0.00','01.00']:
   record=copy.deepcopy(self.record);record['raw_pnl']=value
   with self.assertRaises(ValueError):self.run_record(record)
 def test_unknown_basis_and_fields_refused(self):
  for change in [{'calculation_basis':'AUTO'},{'pnl':'10.00'},{'schema':'unknown'}]:
   with self.assertRaises(ValueError):self.run_record(dict(self.record,**change))
 def test_no_mutation_and_determinism(self):
  before=copy.deepcopy((self.record,self.profile));a=self.run_record();b=self.run_record();self.assertEqual(a,b);self.assertEqual(before,(self.record,self.profile));a['provenance']['mode']='changed';self.assertEqual(self.record['provenance']['mode'],'HISTORICAL')
 def test_large_exact_arithmetic(self):
  self.record['raw_pnl']='999999999999999999999999999999.00';self.assertEqual(self.run_record()['net_pnl'],'999999999999999999999999999997.25')
 def test_negative_fees_and_unit_mismatch_refused(self):
  for change in [{'fees':'-1.00'},{'unit':'BTC'},{'currency':'USD'}]:
   with self.assertRaises(ValueError):self.run_record(dict(self.record,**change))
 def test_missing_provenance_and_bad_pin_refused(self):
  for key in self.record['provenance']:
   record=copy.deepcopy(self.record);del record['provenance'][key]
   with self.assertRaises(ValueError):self.run_record(record)
  record=copy.deepcopy(self.record);record['provenance']['source_head']='main'
  with self.assertRaises(ValueError):self.run_record(record)

 def test_malformed_admission_container_refused(self):
  for admitted in [self.pin,self.pin+'junk',[self.pin],None,{self.pin,1}]:
   with self.assertRaises(ValueError):self.m.convert(self.record,self.profile,admitted)
 def test_empty_objects_refused(self):
  with self.assertRaises(ValueError):self.run_record({})
  with self.assertRaises(ValueError):self.run_record(profile={})
 def test_scale_endpoints(self):
  for scale in [0,18]:
   profile=dict(self.profile,decimal_places=scale);pin=digest(profile)
   unit=lambda n: str(n)+('.'+'0'*scale if scale else '')
   record=dict(self.record,profile_sha256=pin,raw_pnl=unit(10),fees=unit(1),slippage=unit(1),funding=unit(1))
   self.assertEqual(self.m.convert(record,profile,{pin})['net_pnl'],unit(7))
 def test_result_overflow_refused(self):
  profile=dict(self.profile,max_digits=3);pin=digest(profile)
  record=dict(self.record,profile_sha256=pin,raw_pnl='9.99',fees='0.00',slippage='0.00',funding='-0.01')
  with self.assertRaises(ValueError):self.m.convert(record,profile,{pin})
 def test_wrong_scale_and_negative_slippage_refused(self):
  for change in [{'raw_pnl':'1.0'},{'raw_pnl':'1.000'},{'slippage':'-0.01'}]:
   with self.assertRaises(ValueError):self.run_record(dict(self.record,**change))
 def test_unknown_profile_schema_refused(self):
  profile=dict(self.profile,schema='unknown');pin=digest(profile)
  with self.assertRaises(ValueError):self.m.convert(dict(self.record,profile_sha256=pin),profile,{pin})

 def test_ascii_code_boundaries(self):
  for value in ['EUR€','two words','a\n','a\t','/leading','%20','a\\b','a"b','a'*129]:
   for key in ['strategy_id','strategy_version']:
    record=copy.deepcopy(self.record);record['provenance'][key]=value
    with self.assertRaises(ValueError):self.run_record(record)
   for key in ['currency','unit','profile_id']:
    profile=dict(self.profile,**{key:value});pin=digest(profile);record=dict(self.record,profile_sha256=pin)
    if key!='profile_id':record[key]=value
    with self.assertRaises(ValueError):self.m.convert(record,profile,{pin})
 def test_explicit_v2_only_and_distinct_profile_case(self):
  profile=dict(self.profile,profile_id='fixture');pin=digest(profile)
  self.assertNotEqual(pin,self.pin)
  with self.assertRaises(ValueError):self.m.convert(dict(self.record,profile_sha256=pin),profile,{self.pin})
  for change in [{'schema':'agent7.financial-input.v1'}]:
   with self.assertRaises(ValueError):self.run_record(dict(self.record,**change))
  profile=dict(self.profile,schema='agent7.financial-unit-profile.v1');pin=digest(profile)
  with self.assertRaises(ValueError):self.m.convert(dict(self.record,profile_sha256=pin),profile,{pin})

if __name__=='__main__':unittest.main()
