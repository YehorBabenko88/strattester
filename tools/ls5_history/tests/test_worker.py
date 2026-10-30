import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import worker
class Tests(unittest.TestCase):
 def setUp(self):
  import tempfile
  self.fixture=tempfile.TemporaryDirectory();self.original=(worker.ROOT,worker.FROOT,worker.RUN,worker.BATCH)
  worker.ROOT=Path(self.fixture.name);worker.FROOT=worker.ROOT/'session';worker.FROOT.mkdir();worker.RUN=worker.FROOT/'attempt-0001';worker.BATCH=worker.FROOT/'batch-0001'
 def tearDown(self):
  worker.ROOT,worker.FROOT,worker.RUN,worker.BATCH=self.original;self.fixture.cleanup()

 def test_exact_writer_path_and_readonly_uri(self):
  worker.guard('sqlite3.connect',(worker.BATCH/'history.sqlite3',))
  worker.guard('sqlite3.connect',(str(worker.BATCH/'history.sqlite3'),))
  worker.guard('sqlite3.connect',((worker.FROOT/'batch-0001/history.sqlite3').as_uri()+'?mode=ro',))
  for value in [':memory:',str(worker.ROOT/'stage-d-history-01/data/history.sqlite3'),(worker.BATCH/'history.sqlite3').as_uri()+'?mode=rwc']:
   with self.assertRaises(RuntimeError):worker.guard('sqlite3.connect',(value,))
 def test_unadmitted_network_subprocess_and_mutation(self):
  for event,args in [('socket.getaddrinfo',('api.bybit.com',443)),('subprocess.Popen',()),('os.truncate',(str(worker.ROOT/'x'),0)),('open',(str(worker.ROOT/'x'),'w',0))]:
   with self.assertRaises(RuntimeError):worker.guard(event,args)

 def test_actual_sqlite_audit_hook_on_disposable_fixture(self):
  import subprocess,tempfile
  with tempfile.TemporaryDirectory() as d:
   body="import sys,sqlite3;from pathlib import Path;sys.path.insert(0,"+repr(str(Path(__file__).resolve().parents[1]))+");import worker;worker.FROOT=Path("+repr(d)+");worker.BATCH=worker.FROOT/'batch-0001';worker.BATCH.mkdir();sys.addaudithook(worker.guard);c=sqlite3.connect(worker.BATCH/'history.sqlite3');c.execute('create table fixture(x)');c.commit();c.close()"
   result=subprocess.run([sys.executable,'-B','-c',body],capture_output=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
