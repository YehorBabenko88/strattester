import hashlib,json,tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.adapter import load_snapshot,write_snapshot
HEAD='a'*40
def bars():
 return [dict(symbol='SYNTH',open_ms=i*60000,end_ms=(i+1)*60000,available_ms=(i+1)*60000+1,open=100,high=102,low=99,close=101,volume=5) for i in range(4)]
class Fixture:
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'snapshot'
 def tearDown(self):self.tmp.cleanup()
 def make(self):return write_snapshot(self.root,bars(),HEAD)
 def load(self,pin):return load_snapshot(self.root,pin,HEAD,allow_synthetic=True)
 def rewrite(self,name,value):
  data=json.dumps(value,sort_keys=True,separators=(',',':')).encode();(self.root/name).write_bytes(data);return hashlib.sha256(data).hexdigest()

class AdapterTests(Fixture,unittest.TestCase):
 def test_roundtrip_permission_pin_source(self):
  pin=self.make();self.assertEqual(self.load(pin)['bars'],bars())
  for args in ((self.root,pin,HEAD),(self.root,'0'*64,HEAD,True),(self.root,pin,'b'*40,True)):
   with self.assertRaises(ValueError):load_snapshot(*args)
 def test_mutated_content(self):
  pin=self.make();(self.root/'bars.json').write_text('[]')
  with self.assertRaises(ValueError):self.load(pin)
 def test_bad_bars(self):
  for change in ({'available_ms':0},{'end_ms':0},{'close':float('nan')},{'volume':-1},{'open_ms':True},{'symbol':''},{'extra':1}):
   with self.subTest(change=change):
    rows=bars();rows[0].update(change)
    with self.assertRaises(ValueError):write_snapshot(self.root,rows,HEAD)
 def test_order_duplicate_overlap(self):
  for rows in (list(reversed(bars())),bars()+[bars()[-1]],[bars()[0],dict(bars()[1],open_ms=30000)]):
   with self.assertRaises(ValueError):write_snapshot(self.root,rows,HEAD)
 def test_historical_traversal_schema_count_extra(self):
  self.make();original=json.loads((self.root/'manifest.json').read_bytes())
  for change in ({'evidence_class':'HISTORICAL'},{'file':'../bars.json'},{'schema':'native-grid'},{'row_count':99},{'extra':1}):
   m=dict(original);m.update(change);pin=self.rewrite('manifest.json',m)
   with self.assertRaises(ValueError):self.load(pin)
 def test_overwrite(self):
  self.make()
  with self.assertRaises((ValueError,FileExistsError)):self.make()
 def test_json_bounds(self):
  self.make()
  for raw in (b'{"schema":1,"schema":2}',b'{"value":NaN}',b' '*(10*1024*1024+1),b'['*65+b']'*65):
   (self.root/'manifest.json').write_bytes(raw)
   with self.assertRaises(ValueError):self.load(hashlib.sha256(raw).hexdigest())
 def test_links(self):
  pin=self.make();link=Path(self.tmp.name)/'linked'
  try:link.symlink_to(self.root,target_is_directory=True)
  except OSError:self.skipTest('OS symlink privilege unavailable')
  with self.assertRaises(ValueError):load_snapshot(link,pin,HEAD,True)
 def test_extra_file_bad_source(self):
  pin=self.make();(self.root/'extra').write_text('x')
  with self.assertRaises(ValueError):self.load(pin)
  with self.assertRaises(ValueError):write_snapshot(Path(self.tmp.name)/'bad',bars(),'unknown')


class RehashedInputTests(Fixture,unittest.TestCase):
 def test_invalid_bar_with_matching_integrity_hashes(self):
  self.make();rows=bars();rows[0]['available_ms']=0
  data=json.dumps(rows).encode();(self.root/'bars.json').write_bytes(data)
  m=json.loads((self.root/'manifest.json').read_bytes());m.update(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
  pin=self.rewrite('manifest.json',m)
  with self.assertRaises(ValueError):self.load(pin)
 def test_hardlinked_content(self):
  import os
  pin=self.make();other=Path(self.tmp.name)/'hardlink'
  try:os.link(self.root/'bars.json',other)
  except OSError:self.skipTest('OS hardlinks unavailable')
  with self.assertRaises(ValueError):self.load(pin)

class CoverageTests(Fixture,unittest.TestCase):
 def test_coverage_dataset_and_gaps(self):
  rows=[bars()[0],bars()[2]];pin=write_snapshot(self.root,rows,HEAD)
  value=self.load(pin);m=value['manifest']
  self.assertEqual(value['bars'],rows)
  self.assertEqual(m['missingness'],'GAPS_PRESENT')
  self.assertEqual(m['coverage'],[dict(symbol='SYNTH',start_ms=0,end_ms=180000,min_available_ms=60001,max_available_ms=180001,interval_ms=60000,gaps=1)])
  self.assertEqual(m['dataset_id'],m['sha256'])
 def test_rehashed_wrong_coverage(self):
  self.make();m=json.loads((self.root/'manifest.json').read_bytes());m['coverage'][0]['end_ms']+=1
  with self.assertRaises(ValueError):self.load(self.rewrite('manifest.json',m))
 def test_mixed_intervals(self):
  rows=bars();rows[-1].update(end_ms=300000,available_ms=300001)
  with self.assertRaises(ValueError):write_snapshot(self.root,rows,HEAD)
 def test_expected_window(self):
  from mwi_offline.adapter import validate_window
  pin=self.make();value=self.load(pin)
  validate_window(value,0,240000)
  with self.assertRaises(ValueError):validate_window(value,0,300000)

if __name__=='__main__':unittest.main()
