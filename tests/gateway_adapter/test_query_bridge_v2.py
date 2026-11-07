"""Disposable RED only; retained actual query bytes are not authority grants."""
import copy, hashlib, json, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/gateway_adapter'))
from support import canonical, seal, load_adapter, reference, source_root
CAPTURE=pathlib.Path(__file__).parent/'query_v2_capture'
GRID='f19f7feee0f63da34a20607a8cae59191180aa7c'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def captured():
 a=(CAPTURE/'onebar-request.json').read_bytes()
 b=(CAPTURE/'onebar-result.json').read_bytes()
 assert len(a)==917 and sha(a)=='004de0e4d15860dec5d28c179bf3b4e18905e42e61ce23a85f1b28e2633a9c27'
 assert len(b)==1810 and sha(b)=='f68a558021205e79b2ee61d5b4d636dc13aeefb75521e4ca11c6d28f315d73e5'
 return a,b
def wrapper(a,b):
 upstream=json.loads(b); query=json.loads(a)
 rows=[]
 for row in upstream['rows']:
  t,o,h,l,c,v,turnover=map(int,row)
  rows.append(dict(event_start_ms=t,event_end_ms=t+60000,open=o,high=h,low=l,close=c,volume=v))
 p=seal(dict(schema='meta.ohlcv.research.request.v1',venue='bybit',market_type='linear',symbol='BTCUSDT',timeframe='1m',units={'price':'USDT/BTC','volume':'BTC'},start_ms=int(query['range']['start_ms']),end_ms=int(query['range']['end_ms']),as_of_ms=180000,evidence_class='SYNTHETIC',source=dict(kind='HISTORICAL_BACKFILL',identity='root_synthetic_onebar_query_meta_v2',source_revision=GRID,retrieval_id='root-onebar-v2-read-20261107',retrieved_at_ms=120000,raw_sha256=sha(b)),rows=rows))
 return dict(schema='stratt.gateway.synthetic.research.request.v2-review1',operation='meta.ohlcv.untouched_levels.v1',experiment={'id':'fixture.gateway.query.levels','revision':'1'},payload=p,decision_ms=180000,analysis_now_ms=240000,upstream_binding={'query_request_sha256':sha(a),'query_result_sha256':sha(b),'query_implementation_head':GRID})
class QueryBridgeTests(unittest.TestCase):
 def setUp(self):self.m=load_adapter()
 def callable(self):
  fn=getattr(self.m,'execute_query_synthetic_research',None)
  self.assertTrue(callable(fn),'v2 callable is not implemented; frozen review1 remains separate')
  return fn
 def execute(self,fn,q,a,b):return fn(canonical(q),upstream_query_request_bytes=a,upstream_query_result_bytes=b,meta_source_root=str(source_root()),cancel_check=lambda:False)
 def test_actual_fresh_one_bar_result_computed_with_full_lineage(self):
  a,b=captured();q=wrapper(a,b);fn=self.callable();out=self.execute(fn,q,a,b)
  self.assertEqual(out['artifact_bytes'],canonical(reference(q)))
  d=out['descriptor'];self.assertEqual(d['schema'],'stratt.gateway.synthetic.research.result.v2-review1')
  self.assertEqual(d['upstream_binding']['query_request_sha256'],sha(a))
  self.assertEqual(d['upstream_binding']['query_result_sha256'],sha(b))
  self.assertEqual(d['upstream_binding']['request'],json.loads(a))
  self.assertIsNone(d['financial']['net_pnl'])
  self.assertEqual([(x['kind'],x['price'],x['source_start_ms']) for x in json.loads(out['artifact_bytes'])['levels']],[('high','102',0),('low','99',0)])
  self.assertEqual(out,self.execute(fn,q,a,b))
  self.assertEqual(d['upstream_binding']['result_metadata']['publication'],'UNPROVEN')
 def test_original_actual_gap_result_refused_without_slicing(self):
  p=CAPTURE
  a=(p/'gap-request.json').read_bytes();b=(p/'gap-result.json').read_bytes()
  self.assertEqual(sha(a),'93fe1fab8db7d1986d1a5e045806e1872202dd6781faf6e3df095f09a7e48606')
  self.assertEqual(sha(b),'99b18d85c13dfcf4c9a3e50be83082d48a4dcd004687636ee782415b8bfc3d03')
  fn=self.callable()
  with self.assertRaises(self.m.GatewayResearchError):self.execute(fn,wrapper(a,b),a,b)
 def test_foreign_byte_subclass_refused_before_caller_protocol(self):
  class Foreign(bytes):
   def __len__(self):raise AssertionError('foreign length protocol invoked')
  a,b=captured();q=wrapper(a,b);fn=self.callable()
  with self.assertRaises(self.m.GatewayResearchError):self.execute(fn,q,Foreign(a),b)
 def test_upstream_request_over_16k_refused(self):
  a,b=captured();q=wrapper(a,b);fn=self.callable()
  with self.assertRaises(self.m.GatewayResearchError):self.execute(fn,q,b' '*16385,b)
 def invalid(self,q,a,b,code=None):
  with self.assertRaises(self.m.GatewayResearchError) as caught:self.execute(self.callable(),q,a,b)
  if code:self.assertEqual(caught.exception.code,code)
 def test_hash_mismatch_refused(self):
  a,b=captured();q=wrapper(a,b);q['upstream_binding']['query_result_sha256']='0'*64
  self.invalid(q,a,b,'INVALID_REQUEST')
 def test_original_incompatible_root_label_is_not_normalized(self):
  a,b=captured();q=wrapper(a,b);q['payload']['source']['identity']='root.synthetic.onebar.query-meta.v2';seal(q['payload'])
  self.invalid(q,a,b,'INVALID_OHLCV')
 def test_cancel_after_actual_meta_discards_v2_result(self):
  a,b=captured();q=canonical(wrapper(a,b));state=[];previous=sys.getprofile()
  def observe(frame,event,arg):
   if event=='return' and frame.f_code.co_name=='analyze_ohlcv_research':state.append('computed')
  try:
   sys.setprofile(observe)
   with self.assertRaises(self.m.GatewayResearchCancelled):self.callable()(q,upstream_query_request_bytes=a,upstream_query_result_bytes=b,meta_source_root=str(source_root()),cancel_check=lambda:bool(state))
  finally:sys.setprofile(previous)
  self.assertEqual(state,['computed'])
 def test_typed_request_context_join_mismatch_refused(self):
  a,b=captured();r=json.loads(b);r['request']['consumer_context']['view_id']='00000000-0000-4000-8000-000000000099';b=canonical(r)
  self.invalid(wrapper(a,b),a,b,'INVALID_REQUEST')
 def test_profile_unknown_even_with_rehashed_request_refused(self):
  a,b=captured();request=json.loads(a);request['query_profile_sha256']='0'*64;a=canonical(request)
  r=json.loads(b);r['request']=request;r['request_sha256']=sha(a);b=canonical(r)
  self.invalid(wrapper(a,b),a,b,'INVALID_REQUEST')
 def test_fractional_unused_turnover_refused(self):
  a,b=captured();q=wrapper(a,b);r=json.loads(b);r['rows'][0][6]='301.5';b=canonical(r)
  q['upstream_binding']['query_result_sha256']=sha(b)
  self.invalid(q,a,b,'INVALID_REQUEST')
 def test_resealed_meta_payload_row_mismatch_refused(self):
  a,b=captured();q=wrapper(a,b);q['payload']['rows'][0]['close']=100;seal(q['payload'])
  self.invalid(q,a,b,'INVALID_OHLCV')
 def test_future_event_cut_refused(self):
  a,b=captured();request=json.loads(a);request['event_cut_ms']='180000';a=canonical(request)
  r=json.loads(b);r['request']=request;r['request_sha256']=sha(a);b=canonical(r)
  self.invalid(wrapper(a,b),a,b,'INVALID_REQUEST')
 def test_false_flag_numeric_zero_refused(self):
  a,b=captured();r=json.loads(b);r['native_authenticated']=0;b=canonical(r)
  self.invalid(wrapper(a,b),a,b,'INVALID_REQUEST')
 def test_schema_unknown_and_extra_field_refused(self):
  a,b=captured()
  for change in ({'schema':'future'},{'authority':True}):
   r=json.loads(b);r.update(change);changed=canonical(r)
   self.invalid(wrapper(a,changed),a,changed,'INVALID_REQUEST')
 def test_preflight_before_hash_decode_for_all_inputs(self):
  a,b=captured();q=canonical(wrapper(a,b));calls=[];previous=sys.getprofile()
  def observe(frame,event,arg):
   if event=='call' and frame.f_code.co_name in ('_sha','_query_json'):calls.append(frame.f_code.co_name)
  try:
   sys.setprofile(observe)
   for raw,request_raw,result_raw in ((b' '*131073,a,b),(q,b' '*16385,b),(q,a,b' '*1048577)):
    with self.assertRaises(self.m.GatewayResearchError):self.callable()(raw,upstream_query_request_bytes=request_raw,upstream_query_result_bytes=result_raw,meta_source_root='not-read',cancel_check=lambda:False)
  finally:sys.setprofile(previous)
  self.assertEqual(calls,[])
 def test_strict_bool_cancel_without_foreign_disposal(self):
  a,b=captured();q=canonical(wrapper(a,b));sentinel=[]
  class Pause:
   def __await__(self):yield 'owner-suspended'
  async def foreign():
   try:await Pause()
   finally:sentinel.append('creator-finally')
  coroutine=foreign();coroutine.send(None)
  try:
   for value in (0,None,coroutine):
    with self.assertRaises(self.m.GatewayResearchError) as caught:self.callable()(q,upstream_query_request_bytes=a,upstream_query_result_bytes=b,meta_source_root='not-read',cancel_check=lambda:value)
    self.assertEqual(caught.exception.code,'INVALID_CANCEL_CHECK')
   self.assertEqual(sentinel,[])
  finally:coroutine.close()
  self.assertEqual(sentinel,['creator-finally'])
if __name__=='__main__':unittest.main(verbosity=2)
