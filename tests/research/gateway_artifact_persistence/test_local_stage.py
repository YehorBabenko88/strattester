"""LOCAL byte staging only; no simulated positive authority receipt."""
import hashlib,json,pathlib
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from threading import Event
import sys,sqlite3
from strattester.persistence.result_store import ResultStore
ROOT=pathlib.Path(__file__).resolve().parents[3]
PACKET=ROOT/'docs/gateway/research/evidence/btc-v1'
def stage(store,stage_id='stage-local',run_id='run-local',raw=None):
 fn=getattr(store,'stage_gateway_artifact',None)
 assert callable(fn),'local artifact staging is not implemented'
 descriptor=(PACKET/'descriptor.json').read_bytes() if raw is None else raw
 return fn(stage_id,run_id,'BTCUSDT','meta.ohlcv.untouched_levels.v1','1',descriptor,artifact_sha256='f4997d7d26211676cd8664e53d7999f8b71f203510f3b9a275b439c403e03940',original_intent_sha256='a'*64)
def test_exact_raw_stage_retry_and_reopen(tmp_path):
 path=tmp_path/'own.sqlite';s=ResultStore.open(path)
 try:assert stage(s) is None;assert stage(s) is None
 finally:s.close()
 s=ResultStore.open(path)
 try:
  assert stage(s) is None
  rows=s.con.execute("SELECT artifact_descriptor,artifact_descriptor_sha256,result_kind FROM staged_research_results WHERE stage_id='stage-local'").fetchall()
  raw=(PACKET/'descriptor.json').read_bytes()
  assert rows==[(raw,hashlib.sha256(raw).hexdigest(),'ARTIFACT')]
 finally:s.close()
def test_conflicting_same_stage_does_not_replace(tmp_path):
 s=ResultStore.open(tmp_path/'own.sqlite')
 try:
  stage(s)
  with pytest.raises(ValueError,match='ARTIFACT_STAGE_CONFLICT'):stage(s,raw=b'other local opaque bytes')
  assert s.con.execute('SELECT artifact_descriptor FROM staged_research_results').fetchone()[0]==(PACKET/'descriptor.json').read_bytes()
 finally:s.close()
def test_conflicting_logical_identity_under_new_stage_rejected(tmp_path):
 s=ResultStore.open(tmp_path/'own.sqlite')
 try:
  stage(s)
  with pytest.raises(ValueError,match='ARTIFACT_STAGE_CONFLICT'):stage(s,stage_id='different-stage',raw=b'conflict')
 finally:s.close()
def test_legacy_recovery_cleanup_discard_cannot_publish_unknown_artifact(tmp_path):
 s=ResultStore.open(tmp_path/'own.sqlite');called=[]
 try:
  stage(s)
  assert s.promote('stage-local',lambda:called.append('promote') or True) is False
  assert s.recover_staged(lambda *args:called.append('recover') or True)=={'promoted':0,'discarded':0}
  assert s.cleanup_staged(10**12)==0
  s.discard_stage('stage-local')
  assert s.con.execute('SELECT COUNT(*) FROM staged_research_results').fetchone()[0]==1
  assert s.latest('BTCUSDT','meta.ohlcv.untouched_levels.v1') is None
  assert s.latest_fenced('BTCUSDT','meta.ohlcv.untouched_levels.v1',lambda *args:called.append('read') or True) is None
  assert called==[]
 finally:s.close()
def test_legacy_stage_cannot_replace_artifact_stage(tmp_path):
 s=ResultStore.open(tmp_path/'own.sqlite')
 try:
  stage(s)
  with pytest.raises(ValueError,match='ARTIFACT_STAGE_CONFLICT'):s.stage('stage-local','financial','BTCUSDT','A','1',{'net_pnl':999})
 finally:s.close()
def test_projection_and_read_refuse_without_touching_foreign_objects(tmp_path):
 s=ResultStore.open(tmp_path/'own.sqlite');called=[]
 class Foreign:
  def __getattribute__(self,name):called.append(name);raise AssertionError('foreign object inspected')
  def __call__(self):called.append('called');raise AssertionError('foreign callback invoked')
 try:
  stage(s)
  project=getattr(s,'project_gateway_artifact_commit',None);read=getattr(s,'read_gateway_artifact',None)
  assert callable(project) and callable(read),'unavailable authority denial surfaces missing'
  for value in (None,{'state':'COMMITTED'},Foreign()):
   with pytest.raises(RuntimeError,match='ARTIFACT_AUTHORITY_ABI_UNAVAILABLE'):project('stage-local',actual_receipt_handle=value,expected_authority=value)
  with pytest.raises(RuntimeError,match='ARTIFACT_AUTHORITY_ABI_UNAVAILABLE'):read('run-local','BTCUSDT','meta.ohlcv.untouched_levels.v1','1')
  assert called==[] and s.con.execute('SELECT COUNT(*) FROM research_results').fetchone()[0]==0
 finally:s.close()

@pytest.mark.parametrize('change',['identical','descriptor','intent','artifact'])
def test_two_connections_serialize_retry_and_conflict(tmp_path,change):
 path=tmp_path/'own.sqlite';ResultStore.open(path).close();barrier=Barrier(2)
 raw=(PACKET/'descriptor.json').read_bytes()
 def worker(index):
  s=ResultStore.open(path)
  try:
   barrier.wait(timeout=10)
   kw=dict(artifact_sha256='f'*64,original_intent_sha256='a'*64)
   data=raw
   if index==1:
    if change=='descriptor':data=b'conflicting opaque bytes'
    elif change=='intent':kw['original_intent_sha256']='b'*64
    elif change=='artifact':kw['artifact_sha256']='e'*64
   try:s.stage_gateway_artifact('stage-local','run-local','BTCUSDT','meta.ohlcv.untouched_levels.v1','1',data,**kw);return 'staged'
   except ValueError as exc:assert str(exc)=='ARTIFACT_STAGE_CONFLICT';return 'conflict'
  finally:s.close()
 with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(worker,(0,1)))
 assert sorted(out)==(['staged','staged'] if change=='identical' else ['conflict','staged'])
 s=ResultStore.open(path)
 try:assert s.con.execute('SELECT COUNT(*) FROM staged_research_results').fetchone()[0]==1
 finally:s.close()

def test_two_connections_legacy_put_and_artifact_stage_cannot_cross_replace(tmp_path):
 path=tmp_path/'own.sqlite';ResultStore.open(path).close();barrier=Barrier(2)
 def worker(kind):
  s=ResultStore.open(path)
  try:
   barrier.wait(timeout=10)
   try:
    if kind=='artifact':stage(s)
    else:s.put('run-local','BTCUSDT','meta.ohlcv.untouched_levels.v1','1',{'net_pnl':999})
    return 'accepted'
   except ValueError as exc:assert str(exc)=='ARTIFACT_STAGE_CONFLICT';return 'conflict'
  finally:s.close()
 with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(worker,('artifact','financial')))
 assert sorted(out)==['accepted','conflict']
 s=ResultStore.open(path)
 try:assert sum(s.con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('research_results','staged_research_results'))==1
 finally:s.close()

def test_helper_matches_actual_artifact_and_refuses_corruption_before_stage(tmp_path):
 import strattester.research.result_persistence as module
 helper=getattr(module,'stage_gateway_research_artifact',None)
 assert callable(helper),'local artifact staging helper is missing'
 raw=(PACKET/'descriptor.json').read_bytes();artifact=(PACKET/'meta-result.json').read_bytes()
 s=ResultStore.open(tmp_path/'own.sqlite')
 try:
  args=(s,'stage-local','run-local','BTCUSDT','meta.ohlcv.untouched_levels.v1','1')
  for descriptor,payload in ((raw,artifact+b'x'),(raw,b'x'*1048576),(raw.replace(b'v1-review1',b'v999-review1'),artifact)):
   with pytest.raises(ValueError):helper(*args,descriptor,payload,original_intent_sha256='a'*64)
   assert s.con.execute('SELECT COUNT(*) FROM staged_research_results').fetchone()[0]==0
  assert helper(*args,raw,artifact,original_intent_sha256='a'*64) is None
  assert s.con.execute('SELECT publication_receipt FROM staged_research_results').fetchone()==(None,)
 finally:s.close()

def test_cleanup_cannot_delete_concurrently_reused_artifact_stage_id(tmp_path):
 path=tmp_path/'own.sqlite';s=ResultStore.open(path)
 s.stage('stage-local','legacy','BTCUSDT','A','1',{},created_at=1)
 selected=Event();finished=Event()
 def worker():
  other=ResultStore.open(path)
  try:
   assert selected.wait(10)
   other.discard_stage('stage-local');stage(other)
  finally:other.close();finished.set()
 previous=sys.getprofile()
 def observer(frame,event,arg):
  if frame.f_code.co_name=='cleanup_staged' and event=='c_return' and getattr(arg,'__name__','')=='fetchall':
   selected.set();finished.wait(.3)
 try:
  with ThreadPoolExecutor(max_workers=1) as pool:
   future=pool.submit(worker)
   try:sys.setprofile(observer);s.cleanup_staged(10**12)
   finally:sys.setprofile(previous)
   future.result(timeout=10)
  assert s.con.execute("SELECT result_kind FROM staged_research_results WHERE stage_id='stage-local'").fetchall()==[('ARTIFACT',)]
 finally:s.close()

def test_old_database_migration_preserves_actual_row_bytes(tmp_path):
 path=tmp_path/'legacy.sqlite';con=sqlite3.connect(path)
 con.execute('CREATE TABLE research_results(run_id TEXT,symbol TEXT,strategy_id TEXT,strategy_version TEXT,created_at REAL,metrics TEXT,PRIMARY KEY(run_id,symbol,strategy_id,strategy_version))')
 con.execute("INSERT INTO research_results VALUES('old','BTCUSDT','A','1',1,' {\"net_pnl\": 7} ')")
 con.commit();before=con.execute('SELECT * FROM research_results').fetchone();con.close()
 s=ResultStore.open(path)
 try:
  after=s.con.execute('SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics FROM research_results').fetchone()
  assert after==before
  assert s.con.execute('SELECT result_kind,artifact_descriptor,publication_receipt FROM research_results').fetchone()==('FINANCIAL',None,None)
  assert s.latest('BTCUSDT','A')['metrics']=={'net_pnl':7}
 finally:s.close()

@pytest.mark.parametrize('changed',[
 {'stage_id':'stage\n'}, {'run_id':'x'*129}, {'operation_revision':'1\n'},
 {'operation_revision':str(2**63)}, {'artifact_sha256':'A'*64},
 {'original_intent_sha256':True}, {'raw_descriptor':b'x'*65537},
])
def test_stage_bounds_and_terminal_grammar_refuse_without_rows(tmp_path,changed):
 s=ResultStore.open(tmp_path/'own.sqlite')
 try:
  args=dict(stage_id='local',run_id='run',symbol='BTCUSDT',operation_id='meta',operation_revision='1',raw_descriptor=b'opaque',artifact_sha256='a'*64,original_intent_sha256='b'*64)
  args.update(changed)
  with pytest.raises(ValueError,match='ARTIFACT_STAGE_INVALID'):s.stage_gateway_artifact(**args)
  assert s.con.execute('SELECT COUNT(*) FROM staged_research_results').fetchone()[0]==0
 finally:s.close()

def test_helper_foreign_bytes_preflight_and_duplicate_descriptor_refused(tmp_path):
 from strattester.research.result_persistence import stage_gateway_research_artifact as helper
 class Foreign(bytes):
  def __len__(self):raise AssertionError('foreign length invoked')
 s=ResultStore.open(tmp_path/'own.sqlite');raw=(PACKET/'descriptor.json').read_bytes();artifact=(PACKET/'meta-result.json').read_bytes()
 try:
  args=(s,'s','r','BTCUSDT','meta.ohlcv.untouched_levels.v1','1')
  for descriptor,payload in ((Foreign(raw),artifact),(raw,Foreign(artifact)),(b'{"schema":"duplicate",'+raw[1:],artifact)):
   with pytest.raises(ValueError):helper(*args,descriptor,payload,original_intent_sha256='a'*64)
  assert s.con.execute('SELECT COUNT(*) FROM staged_research_results').fetchone()[0]==0
 finally:s.close()

def test_cross_kind_collisions_cover_both_tables_and_legacy_paths(tmp_path):
 s=ResultStore.open(tmp_path/'own.sqlite')
 try:
  stage(s)
  with pytest.raises(ValueError,match='ARTIFACT_STAGE_CONFLICT'):s.put('run-local','BTCUSDT','meta.ohlcv.untouched_levels.v1','1',{'net_pnl':1})
  assert stage(s,stage_id='retry-different-stage') is None
  assert s.con.execute('SELECT stage_id FROM staged_research_results').fetchall()==[('stage-local',)]
  s.put('financial','BTCUSDT','A','1',{'net_pnl':7})
  with pytest.raises(ValueError,match='ARTIFACT_STAGE_CONFLICT'):s.stage_gateway_artifact('s','financial','BTCUSDT','A','1',b'opaque',artifact_sha256='a'*64,original_intent_sha256='b'*64)
  # Negative corrupt-row fixture, NULL receipt: never a positive authority event.
  s.con.execute("UPDATE research_results SET result_kind='ARTIFACT' WHERE run_id='financial'");s.con.commit()
  assert s.latest('BTCUSDT','A') is None
  assert s.latest_fenced('BTCUSDT','A',lambda *a:True) is None
  for call in (lambda:s.put('financial','BTCUSDT','A','1',{}),lambda:s.stage('new','financial','BTCUSDT','A','1',{})):
   with pytest.raises(ValueError,match='ARTIFACT_STAGE_CONFLICT'):call()
 finally:s.close()

def test_simultaneous_first_upgrade_of_prior_wal_schema(tmp_path):
 for trial in range(16):
  path=tmp_path/('legacy-'+str(trial)+'.sqlite');con=sqlite3.connect(path)
  con.execute('PRAGMA journal_mode=WAL')
  con.execute('CREATE TABLE research_results(run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,strategy_version TEXT NOT NULL,created_at REAL NOT NULL,metrics TEXT NOT NULL,job_id TEXT,lease_token INTEGER NOT NULL DEFAULT 0,node_generation INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(run_id,symbol,strategy_id,strategy_version))')
  con.execute('CREATE TABLE staged_research_results(stage_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,strategy_version TEXT NOT NULL,created_at REAL NOT NULL,metrics TEXT NOT NULL,job_id TEXT,lease_token INTEGER NOT NULL DEFAULT 0,node_generation INTEGER NOT NULL DEFAULT 0)')
  con.execute("INSERT INTO research_results VALUES('old','BTCUSDT','A','1',1,' {\"net_pnl\": 7} ',NULL,0,0)")
  con.commit();con.close();barrier=Barrier(2)
  def worker(_):
   barrier.wait(timeout=10);store=ResultStore.open(path)
   try:return store.latest('BTCUSDT','A')['metrics']
   finally:store.close()
  with ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(worker,(0,1)))==[{'net_pnl':7},{'net_pnl':7}]

def test_failed_incompatible_migration_releases_writer_while_traceback_retained(tmp_path):
 path=tmp_path/'incompatible.sqlite';con=sqlite3.connect(path)
 con.execute('CREATE TABLE research_results(run_id TEXT)');con.commit();con.close()
 retained=[]
 try:ResultStore.open(path)
 except sqlite3.OperationalError as exc:retained.append(exc)
 assert len(retained)==1 and 'no such column: symbol' in str(retained[0])
 writer=sqlite3.connect(path,timeout=0)
 try:
  writer.execute('BEGIN IMMEDIATE')
  assert [r[1] for r in writer.execute('PRAGMA table_info(research_results)')]==['run_id']
 finally:writer.rollback();writer.close()
 assert retained[0].__traceback__ is not None

def test_baseexception_during_initialization_rolls_back_actual_writer(tmp_path):
 class Stop(BaseException):pass
 interrupted=Stop('test-owner interrupt')
 class InterruptedStore(ResultStore):
  @classmethod
  def _initialize(cls,path,con):
   con.execute('BEGIN IMMEDIATE');con.execute('CREATE TABLE not_committed(x)')
   raise interrupted
 path=tmp_path/'interrupted.sqlite';retained=[]
 try:InterruptedStore.open(path)
 except Stop as exc:retained.append(exc)
 assert retained==[interrupted]
 con=sqlite3.connect(path,timeout=0)
 try:
  con.execute('BEGIN IMMEDIATE')
  assert con.execute("SELECT name FROM sqlite_master WHERE name='not_committed'").fetchall()==[]
 finally:con.rollback();con.close()

def test_cleanup_error_does_not_replace_original_baseexception(tmp_path):
 class Stop(BaseException):pass
 original=Stop('preserve original')
 class ClosedDuringInitialization(ResultStore):
  @classmethod
  def _initialize(cls,path,con):con.close();raise original
 retained=[]
 try:ClosedDuringInitialization.open(tmp_path/'closed.sqlite')
 except Stop as exc:retained.append(exc)
 assert retained==[original]
