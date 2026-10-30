import unittest,tempfile,subprocess,sys,json,sqlite3,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_collector as fixtures
Fake=fixtures.Fake
import history_collector as c,history_verify as v
from postrun_acceptance import committed_tip
HERE=Path(__file__).resolve().parents[1]
class Tests(unittest.TestCase):
 def test_actual_abrupt_crash_at_three_publication_boundaries(self):
  for stage,exitcode in [('after_sqlite_commit',91),('after_checkpoint',92),('before_state_commit',93)]:
   with self.subTest(stage=stage),tempfile.TemporaryDirectory() as td:
    root=Path(td)
    code="""import sys,os,json
from pathlib import Path
sys.path[:0]=[PKG,TESTS]
import history_collector as c,history_verify as v
from test_collector import Fake
root=Path(ROOT);f=Fake();old=c.publish
if STAGE=='after_sqlite_commit':
 def stop(*a,**k):os._exit(EXIT)
 v.inspect_database=stop
else:
 def publish(path,value):
  if STAGE=='before_state_commit' and value.get('state')=='COMMITTED':os._exit(EXIT)
  old(path,value)
  if STAGE=='after_checkpoint' and Path(path).name=='checkpoint.json':os._exit(EXIT)
 c.publish=publish
c.run_batch(root,'batch-0001',f,clock_utc_ms=lambda:f.server)
"""
    prefix='PKG='+repr(str(HERE))+';TESTS='+repr(str(HERE/'tests'))+';ROOT='+repr(td)+';STAGE='+repr(stage)+';EXIT='+str(exitcode)+'\n'
    result=subprocess.run([sys.executable,'-B','-c',prefix+code],capture_output=True,timeout=30)
    self.assertEqual(result.returncode,exitcode,result.stderr.decode(errors='replace'))
    self.assertEqual(json.loads((root/'session-state.json').read_text())['state'],'IN_PROGRESS')
    db=root/'batch-0001/history.sqlite3';con=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
    try:self.assertGreater(con.execute('select count(*) from candles').fetchone()[0],0)
    finally:con.close()
    cp=root/'batch-0001/checkpoint.json';pin=c.sha(cp) if cp.exists() else '0'*64
    if cp.exists():
     # Consistency alone is insufficient: preserve this distinction as evidence.
     self.assertEqual(v.verify_checkpoint(cp,pin)['status'],'CHECKPOINT_CONSISTENT')
     with self.assertRaises(ValueError):committed_tip(cp,pin)
    fake=Fake()
    with self.assertRaises((ValueError,FileNotFoundError)):c.run_batch(root,'batch-0002',fake,previous=cp,previous_sha=pin)
    self.assertEqual(fake.calls,[])
 def test_predecessor_missing_tampered_and_substituted_before_fetch(self):
  helper=fixtures.Tests()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);fake=Fake();helper.batch(root,'batch-0001',fake);cp=root/'batch-0001/checkpoint.json';pin=c.sha(cp);before=cp.read_bytes()
   cases=[('missing',None),('corrupt',b'{bad'),('substituted',c.canonical(dict(json.loads(before),session_requests=1)))]
   for name,data in cases:
    with self.subTest(case=name):
     if data is None:cp.unlink()
     else:cp.write_bytes(data)
     f=Fake()
     with self.assertRaises((ValueError,FileNotFoundError)):helper.batch(root,'batch-0002',f,previous=cp,previous_sha=pin)
     self.assertEqual(f.calls,[]);cp.write_bytes(before)
 def test_current_tip_and_repeated_discovery_pagination(self):
  class Paged(Fake):
   def __call__(self,path,p):
    body,meta=super().__call__(path,p)
    if path.endswith('/instruments-info'):
     value=json.loads(body);items=value['result']['list'];value['result']['list']=items[:1] if 'cursor' not in p else items[1:];value['result']['nextPageCursor']='page2' if 'cursor' not in p else ''
     body=json.dumps(value).encode();meta.update(body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
    return body,meta
  helper=fixtures.Tests()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=Paged();one=helper.batch(root,'batch-0001',f);cp=root/'batch-0001/checkpoint.json';pin=c.sha(cp);self.assertEqual(committed_tip(cp,pin)['history_state'],'PARTIAL')
   two=helper.batch(root,'batch-0002',f,previous=cp,previous_sha=pin)
   self.assertEqual((one['batch_requests'],two['batch_requests'],two['session_requests']),(20,20,40));self.assertEqual(sum(path.endswith('/instruments-info') for path,p in f.calls),4)
   with self.assertRaises(ValueError):committed_tip(cp,pin)
 def test_false_ready_and_incomplete_universe(self):
  helper=fixtures.Tests()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=Fake();cpdata=helper.batch(root,'batch-0001',f);forged=root/'batch-0001/forged.json';cpdata['status']='READY';forged.write_bytes(c.canonical(cpdata))
   with self.assertRaises(ValueError):v.verify_checkpoint(forged,c.sha(forged))
  class Incomplete(Fake):
   def __call__(self,path,p):
    body,meta=super().__call__(path,p)
    if path.endswith('/instruments-info'):
     data=json.loads(body);data['result']['nextPageCursor']='repeated';body=json.dumps(data).encode();meta.update(body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
    return body,meta
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=Incomplete()
   with self.assertRaises(ValueError):helper.batch(root,'batch-0001',f)
   self.assertFalse((root/'batch-0001/checkpoint.json').exists());self.assertEqual(json.loads((root/'session-state.json').read_text())['state'],'BLOCKED')

 def test_physical_postrun_resource_and_result_branches_synthetic(self):
  from postrun_acceptance import physical_postrun
  helper=fixtures.Tests()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);fake=Fake();receipt=helper.batch(root,'batch-0001',fake);cp=root/'batch-0001/checkpoint.json';pin=c.sha(cp);attempt=root/'attempt-0001';attempt.mkdir()
   result={'status':'F1_BATCH_VERIFIED','head':c.HEAD,'pid':123,'nonce':'a'*32,'checkpoint_sha256':pin,'batch_index':1,'history_state':'PARTIAL'}
   result_path=attempt/'result.json';result_path.write_bytes(c.canonical(result))
   controller={'status':'F1_BATCH_VERIFIED','controller_exit_code':0,'unexpected_descendant':False,'marker_validation':True,'rate_budget':{'status':'RATE_BUDGET_PASS'},'identity':{'Pid':123,'Created':'111'},'final':{'Pid':123,'Created':'111','ExitCode':0,'Liveness':'EXITED','HasExited':True,'CpuSeconds':1,'PeakBytes':1048576},'wall_seconds':2,'nonce':'a'*32,'functional_result_sha256':c.sha(result_path)}
   controller_path=attempt/'controller.json';controller_path.write_bytes(c.canonical(controller))
   self.assertEqual(physical_postrun(cp,pin,controller_path,c.sha(controller_path),root)['history_state'],'PARTIAL')
   for key,value in [('CpuSeconds',16),('PeakBytes',512*1048576+1),('ExitCode',1),('Liveness','RUNNING'),('CpuSeconds',True)]:
    with self.subTest(field=key,value=value):
     altered=dict(controller,final=dict(controller['final'],**{key:value}));controller_path.write_bytes(c.canonical(altered))
     with self.assertRaises(ValueError):physical_postrun(cp,pin,controller_path,c.sha(controller_path),root)
   controller_path.write_bytes(c.canonical(controller));result['nonce']='b'*32;result_path.write_bytes(c.canonical(result));controller['functional_result_sha256']=c.sha(result_path);controller_path.write_bytes(c.canonical(controller))
   with self.assertRaises(ValueError):physical_postrun(cp,pin,controller_path,c.sha(controller_path),root)
 def test_insufficient_eligibility_remains_partial(self):
  class NewlyListed(Fake):
   def __call__(self,path,p):
    body,meta=super().__call__(path,p)
    if path.endswith('/instruments-info'):
     data=json.loads(body);data['result']['list'][0]['launchTime']=str(self.server);body=json.dumps(data).encode();meta.update(body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
    return body,meta
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);f=NewlyListed();receipt=fixtures.Tests().batch(root,'batch-0001',f)
   self.assertEqual(receipt['status'],'PARTIAL');self.assertNotIn('BTCUSDT',receipt['eligible']);self.assertEqual(receipt['coverage']['BTCUSDT']['1m']['state'],'MISSING')
