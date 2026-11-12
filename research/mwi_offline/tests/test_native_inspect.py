import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.native_inspect import inspect_grid_v11
HEAD='a'*40
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def fixture():
 q=dict(schema='grid.history.request.v1',venue='BYBIT',market_type='linear',symbol='SYNTH',units=dict(price='USDT',volume='base'),start_ms=0,end_ms=60000,as_of_ms=61000,max_age_ms=1000)
 row=dict(open=100,high=102,low=99,close=101,volume=5,event_start_ms=0,event_end_ms=60000,available_at_ms=60010,revision='b'*64,source_event_start_ms=1,source_event_end_ms=59999,watermark_ms=60000,source_receipt_hash='c'*64)
 e=dict(schema='grid.history.v1.1',request=q,source=dict(identity='fixture',source_revision=HEAD,epoch='fixture-epoch'),evidence_class='SYNTHETIC',rows=[row],source_receipts=['c'*64],execution_authority=False,trading_authorized=False,watermark_ms=60000)
 return seal(e)
def seal(e):
 e.pop('dataset_fingerprint',None)
 e['dataset_id']=digest(dict(schema='grid.dataset.v1.1',source=e['source'],identity={k:e['request'][k] for k in ('venue','market_type','symbol','units')},timeframe='1m',representation='historical_aggregate',evidence_class=e['evidence_class'],rows=e['rows'],source_receipts=e['source_receipts']))
 e['dataset_fingerprint']=digest(e);return e
class Checks(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'native.json'
 def tearDown(self):self.tmp.cleanup()
 def inspect(self,e):
  data=json.dumps(e,sort_keys=True,separators=(',',':')).encode();self.path.write_bytes(data)
  return inspect_grid_v11(self.path,hashlib.sha256(data).hexdigest(),HEAD)
 def test_integrity_only_and_historical_blocker(self):
  for kind,status in (('SYNTHETIC','SYNTHETIC'),('HISTORICAL','HISTORICAL_UNATTESTED')):
   e=fixture();e['evidence_class']=kind;r=self.inspect(seal(e))
   self.assertEqual(r['status'],status);self.assertIs(r['training_eligible'],False);self.assertIn('RECEIPT_AUTHENTICITY_NOT_PROVISIONED',r['blockers']);self.assertEqual(r['row_count'],1)
 def test_external_pin(self):
  self.inspect(fixture())
  with self.assertRaises(ValueError):inspect_grid_v11(self.path,'0'*64,HEAD)
 def test_resealed_invalid_fields(self):
  for key,value in (('watermark_ms',60011),('event_end_ms',59999),('source_event_end_ms',60000),('available_at_ms',59999),('revision','bad'),('source_receipt_hash','bad'),('volume',-1),('event_start_ms',True)):
   with self.subTest(key=key):
    e=fixture();e['rows'][0][key]=value
    with self.assertRaises(ValueError):self.inspect(seal(e))
 def test_schema_provenance_identity(self):
  for mutate in (lambda e:e.update(schema='grid.history.v1'),lambda e:e['source'].update(source_revision='d'*40),lambda e:e.update(evidence_class='REAL'),lambda e:e['request'].update(units={'price':'USDT'}),lambda e:e.update(execution_authority=True),lambda e:e.update(source_receipts=['d'*64])):
   e=fixture();mutate(e)
   with self.assertRaises(ValueError):self.inspect(seal(e))
 def test_content_hashes(self):
  for field in ('dataset_id','dataset_fingerprint'):
   e=fixture();e[field]='0'*64
   with self.assertRaises(ValueError):self.inspect(e)
 def test_duplicate_keys_nesting_size_nonfinite(self):
  for raw in (b'{"x":1,"x":2}',b'['*65+b']'*65,b' '*(8*1024*1024+1),b'{"x":NaN}'):
   self.path.write_bytes(raw)
   with self.assertRaises(ValueError):inspect_grid_v11(self.path,hashlib.sha256(raw).hexdigest(),HEAD)
 def test_inspection_preserves_bytes_and_has_no_trainable_bars(self):
  self.inspect(fixture());before=self.path.read_bytes()
  result=inspect_grid_v11(self.path,hashlib.sha256(before).hexdigest(),HEAD)
  self.assertEqual(before,self.path.read_bytes());self.assertNotIn('bars',result);self.assertNotIn('rows',result)
if __name__=='__main__':unittest.main()
