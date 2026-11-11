"""Focused actual-Meta synthetic calculation; no signature/authority mocks."""
import copy,json,pathlib,sys,tempfile,types,unittest
from support import canonical,sha,request,reference,source_root,load_adapter,copy_source,copy_source_record,copied_source_admission_diagnostics
EXPECTED=[('low','8',0),('low','9',60000),('high','12',120000),('low','10',120000)]

class ExistingMetaReferenceTests(unittest.TestCase):
 def test_real_meta_hand_calculated_btc_levels(self):
  q=request();original=copy.deepcopy(q);out=reference(q)
  self.assertEqual([(x['kind'],x['price'],x['source_start_ms']) for x in out['levels']],EXPECTED)
  self.assertEqual(out['symbol'],'BTCUSDT');self.assertEqual(q,original)
  self.assertEqual(out['source_authenticity'],'NOT_EVALUATED');self.assertFalse(out['execution_authority'])
 def test_real_meta_repeat_exact_bytes(self):
  q=request();self.assertEqual(canonical(reference(q)),canonical(reference(q)))

class GatewayAdapterTests(unittest.TestCase):
 def setUp(self):self.m=load_adapter()
 def execute(self,q=None,*,cancel_check=lambda:False,root=None,raw=None):
  return self.m.execute_synthetic_research(canonical(request() if q is None else q) if raw is None else raw,meta_source_root=str(source_root() if root is None else root),cancel_check=cancel_check)
 def refused(self,q=None,**kwargs):
  with self.assertRaises(self.m.GatewayResearchError):self.execute(q,**kwargs)
 def test_actual_result_equals_real_meta_and_provenance(self):
  q=request();before=copy.deepcopy(q);result=self.execute(q)
  self.assertEqual(set(result),{'descriptor','artifact_bytes'})
  self.assertIs(type(result['artifact_bytes']),bytes)
  self.assertEqual(result['artifact_bytes'],canonical(reference(q)))
  d=result['descriptor'];self.assertEqual(d['schema'],'stratt.gateway.synthetic.research.result.v1-review1')
  self.assertEqual(d['state'],'COMPUTED_TEST_ONLY');self.assertEqual(d['request_raw_sha256'],sha(canonical(q)))
  self.assertEqual(d['artifact']['raw_sha256'],sha(result['artifact_bytes']))
  self.assertEqual(d['artifact']['byte_count'],str(len(result['artifact_bytes'])))
  self.assertEqual(d['provenance']['meta_head'],'f3c01a23fa5baaeeeb28eb8e9397e72b5ef4d5a1')
  self.assertEqual(d['provenance']['dataset_revision'],'UNAVAILABLE_A4_BINDING_PENDING')
  self.assertEqual(d['series_semantics']['rows'],'INPUT_REPLAY_NOT_DERIVED')
  for field in ('gross_pnl','net_pnl','fees','slippage','signed_funding','currency','scale'):self.assertIsNone(d['financial'][field])
  self.assertFalse(d['execution_authority']);self.assertFalse(d['trading_authorized']);self.assertFalse(d['training_authorized'])
  self.assertEqual(q,before)
 def test_replay_same_bytes_clock_and_input_unchanged(self):
  q=request();self.assertEqual(self.execute(q),self.execute(copy.deepcopy(q)))
 def test_dataset_digest_mismatch_refused(self):
  q=request();q['payload']['dataset_id']='0'*64;self.refused(q)
 def test_schema_operation_unknown_fields_refused(self):
  for change in ({'schema':'unknown'},{'operation':'eval'},{'fees':'0'},{'execution_authority':True}):self.refused(dict(request(),**change))
 def test_non_synthetic_refused_even_resealed(self):
  from support import seal
  q=request();q['payload']['evidence_class']='HISTORICAL';seal(q['payload']);self.refused(q)
 def test_finite_and_shape_bounds_refused(self):
  from support import seal
  for key,value in [('close',True),('high',1e16),('low',0),('volume',-1)]:
   q=request();q['payload']['rows'][0][key]=value;seal(q['payload']);self.refused(q)
  q=request();q['payload']['rows'][1]['event_start_ms']=120000;seal(q['payload']);self.refused(q)
  for value in [float('nan'),float('inf')]:
   q=request();q['payload']['rows'][0]['close']=value
   self.refused(raw=json.dumps(q,allow_nan=True).encode())
 def test_duplicate_json_keys_refused(self):
  raw=canonical(request());self.refused(raw=b'{"schema":"stratt.gateway.synthetic.research.request.v1-review1",'+raw[1:])
 def test_request_and_row_budget_refused(self):
  self.refused(raw=b' '*131073)
  q=request();q['payload']['rows']*=86;self.refused(q)
 def test_cancel_before_calculation_returns_no_result(self):
  with self.assertRaises(self.m.GatewayResearchCancelled):self.execute(cancel_check=lambda:True)
 def test_cancel_after_real_meta_call_discards_result(self):
  state={'returned':False};old=sys.getprofile()
  def observer(frame,event,arg):
   if event=='return' and frame.f_code.co_name=='analyze_ohlcv_research' and frame.f_code.co_filename.endswith('ohlcv_research_adapter.py'):state['returned']=True
  try:
   sys.setprofile(observer)
   with self.assertRaises(self.m.GatewayResearchCancelled):self.execute(cancel_check=lambda:state['returned'])
  finally:sys.setprofile(old)
  self.assertTrue(state['returned'])
 def test_cancel_hook_requires_exact_bool_and_no_awaitable(self):
  for value in [None,0,1,'false',[]]:self.refused(cancel_check=lambda value=value:value)
  async def async_hook():return False
  self.refused(cancel_check=async_hook)
  def raises():raise RuntimeError('caller cancellation check failed')
  self.refused(cancel_check=raises)
 def test_foreign_suspended_coroutine_not_finalized_by_refusal(self):
  sentinel=[]
  class Pause:
   def __await__(self):yield 'owner-suspended'
  async def foreign():
   try:await Pause()
   finally:sentinel.append('owner-finalized')
  coroutine=foreign();coroutine.send(None)
  try:
   self.refused(cancel_check=lambda:coroutine)
   self.assertEqual(sentinel,[])
  finally:coroutine.close() # Only the actual test owner may dispose its object.
  self.assertEqual(sentinel,['owner-finalized'])
 def test_source_pin_mismatch_refused(self):
  with tempfile.TemporaryDirectory() as directory:
   root=copy_source(directory);p=root/'src/meta_analyse/core.py';p.write_bytes(p.read_bytes()+b'\n# altered source\n');self.refused(root=root)
 def test_source_cache_and_shadow_refused(self):
  for shadow in ['json.py','__pycache__/core.pyc']:
   with tempfile.TemporaryDirectory() as directory:
    root=copy_source(directory);p=root/'src/meta_analyse'/shadow;p.parent.mkdir(exist_ok=True);p.write_bytes(b'raise RuntimeError("shadow executed")');self.refused(root=root)
 def test_preloaded_meta_namespace_refused(self):
  name='meta_analyse.headless_service';previous=sys.modules.get(name);sys.modules[name]=types.ModuleType(name)
  try:self.refused()
  finally:
   if previous is None:sys.modules.pop(name,None)
   else:sys.modules[name]=previous
 def test_source_changed_after_calculation_refused(self):
  with tempfile.TemporaryDirectory() as directory:
   root=copy_source(directory)
   self.assertEqual(copy_source_record(root),{'schema':'gateway.test.owned-copy.v1','ordinary_ancestry':True,'same_physical_directory':True,'canonical_identity_equal':True,'empty_before_copy':True,'source_pins_verified':True})
   self.assertEqual(root.resolve(strict=True),root.absolute())
   facts=copied_source_admission_diagnostics(root)
   # The SAME copy must calculate successfully before testing its later mutation.
   # Do not resolve/rewrite this path to bypass a production admission refusal.
   try:calibration=self.execute(root=root)
   except self.m.GatewayResearchError as exc:
    code=exc.code if exc.code in ('SOURCE_UNAVAILABLE','INVALID_REQUEST','INVALID_OHLCV','RESULT_UNAVAILABLE') else 'OTHER_CLOSED_CODE'
    raise self.failureException(json.dumps({'phase':'COPY_POSITIVE_CALIBRATION','code':code,'facts':facts},sort_keys=True)) from None
   except Exception:
    raise self.failureException(json.dumps({'phase':'COPY_POSITIVE_CALIBRATION','code':'UNEXPECTED_CLOSED_ERROR','facts':facts},sort_keys=True)) from None
   self.assertEqual(calibration['artifact_bytes'],canonical(reference(request())))
   self.assertFalse(calibration['descriptor']['execution_authority'])
   state={'changed':False,'entered_meta':False};old=sys.getprofile()
   def observer(frame,event,arg):
    actual=frame.f_code.co_name=='analyze_ohlcv_research' and frame.f_code.co_filename==str(root/'src/meta_analyse/ohlcv_research_adapter.py')
    if actual and event=='call':state['entered_meta']=True
    if actual and event=='return' and not state['changed']:
     p=root/'src/meta_analyse/core.py';p.write_bytes(p.read_bytes()+b'\n# changed during calculation\n');state['changed']=True
   try:
    sys.setprofile(observer)
    with self.assertRaises(self.m.GatewayResearchError) as refused:self.execute(root=root)
   finally:sys.setprofile(old)
   diagnostic=json.dumps({'phase':'MUTATION_REFUSAL','entered_meta':state['entered_meta'],
                          'changed':state['changed'],'facts':facts},sort_keys=True)
   self.assertTrue(state['changed'],diagnostic)
   self.assertEqual(refused.exception.code,'SOURCE_UNAVAILABLE',diagnostic)

if __name__=='__main__':unittest.main()
