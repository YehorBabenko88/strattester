"""Pure SYNTHETIC node-local ledger exports; no network or exchange authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import patch
import pytest
from strattester.research import quote_paper as paper
from tests.test_quote_paper import fixture,seal


def populated(tmp_path):
 path=tmp_path/'paper.sqlite';ledger=paper.PaperLedger.create(path)
 request=fixture();result=ledger.append(request,now_ms=1300)
 return path,ledger,request,result


def disk_state(parent):
 return {p.name:(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
         for p in parent.iterdir() if p.is_file()}


def test_export_revalidates_at_original_clock_and_never_mutates(tmp_path):
 path,ledger,request,result=populated(tmp_path);before=disk_state(tmp_path)
 with patch.object(paper,'evaluate',wraps=paper.evaluate) as evaluate:
  snapshot=paper.PaperLedger.export(path)
 assert evaluate.call_count==1 and evaluate.call_args.kwargs=={'now_ms':1300}
 assert snapshot['schema']=='stratt.paper.quote.snapshot.v1'
 assert snapshot['validated_count']==snapshot['returned_count']==1 and snapshot['has_more'] is False
 assert snapshot['selection_order']==['admitted_ms DESC','request_id DESC']
 assert snapshot['rows']==[dict(request_id='r1',signal_receipt_id='s1',request_sha256=paper.digest(request),result_sha256=paper.digest(result),admitted_ms=1300,result=result)]
 assert snapshot['source_authenticity']=='NOT_EVALUATED' and snapshot['receipt_provenance']=='CALLER_DECLARED'
 assert not snapshot['execution_authority'] and not snapshot['trading_authorized']
 assert snapshot['missing_state']==['OPEN_POSITIONS','ACCOUNT_EQUITY','BALANCE','UNREALIZED_PNL']
 assert snapshot['rows'][0]['result']['receipt_bindings']==result['receipt_bindings']
 for key in ('grid_normal','paper_eligible','h_b'):assert snapshot['rows'][0]['result'][key]=='NOT_QUALIFIED'
 assert 'request' not in snapshot['rows'][0] and 'generated_at_ms' not in snapshot
 assert ledger.snapshot()==snapshot==paper.PaperLedger.export(path)
 assert disk_state(tmp_path)==before


def test_export_empty_and_deterministic_bounded_selection(tmp_path):
 path=tmp_path/'paper.sqlite';ledger=paper.PaperLedger.create(path)
 empty=ledger.snapshot();assert empty['rows']==[] and empty['validated_count']==0
 for name in ('a','z','m'):
  request=fixture();request['request_id']=name
  request['signal']['receipt_id']='signal-'+name;seal(request['signal'])
  ledger.append(request,now_ms=1300)
 snapshot=ledger.snapshot(limit=2)
 assert [r['request_id'] for r in snapshot['rows']]==['z','m']
 assert snapshot['validated_count']==3 and snapshot['returned_count']==2 and snapshot['has_more']


@pytest.mark.parametrize('change',['arithmetic','receipt','request_hash','hidden_row'])
def test_export_revalidates_every_row_not_just_selected(tmp_path,change):
 path,ledger,request,result=populated(tmp_path)
 with sqlite3.connect(path) as c:
  if change in ('arithmetic','hidden_row'):
   result['pnl']=999;c.execute('UPDATE trades SET result=?,result_sha256=?',(paper.canonical(result).decode(),paper.digest(result)))
   if change=='hidden_row':
    other=fixture();other['request_id']='z';other['signal']['receipt_id']='sz';seal(other['signal'])
    computed=paper.evaluate(other,now_ms=1300)
    c.execute('INSERT INTO trades VALUES(?,?,?,?,?,?,?)',('z','sz',paper.digest(other),1300,paper.digest(computed),paper.canonical(computed).decode(),paper.canonical(other).decode()))
  elif change=='receipt':c.execute("UPDATE receipts SET sha256=? WHERE receipt_id='s1'",('f'*64,))
  else:c.execute("UPDATE trades SET request_sha256=?",('f'*64,))
 before=disk_state(tmp_path)
 with pytest.raises(paper.PaperSnapshotBlocked) as failure:ledger.snapshot(limit=1)
 assert failure.value.code=='PAPER_SNAPSHOT_INVALID' and failure.value.status=='BLOCKED'
 assert disk_state(tmp_path)==before


@pytest.mark.parametrize('kind',['missing','foreign','hardlink','symlink','sidecar_link','dangling_sidecar','wal','shm','journal'])
def test_export_rejects_unsafe_or_unrelated_paths_without_adoption(tmp_path,kind):
 path,ledger,request,result=populated(tmp_path);target=path
 if kind=='missing':target=tmp_path/'absent.sqlite'
 elif kind=='foreign':
  target=tmp_path/'foreign.sqlite'
  with sqlite3.connect(target) as c:c.execute('CREATE TABLE unrelated(value)')
 elif kind=='hardlink':os.link(path,tmp_path/'second-link')
 elif kind=='symlink':
  target=tmp_path/'linked.sqlite'
  try:target.symlink_to(path)
  except OSError:pytest.skip('Symlink creation unavailable')
 else:
  side=Path(str(path)+{'sidecar_link':'-wal','dangling_sidecar':'-wal','wal':'-wal','shm':'-shm','journal':'-journal'}[kind])
  if kind=='sidecar_link':
   foreign=tmp_path/'private-foreign-leaf';foreign.write_bytes(b'NOT_A_SQLITE_WAL_NEVER_READ');os.link(foreign,side)
  elif kind=='dangling_sidecar':
   try:side.symlink_to(tmp_path/'absent-wal-target')
   except OSError:pytest.skip('Symlink creation unavailable')
  else:side.write_bytes(b'UNSUPPORTED_ACTIVE_SQLITE_SIDECAR')
 before=disk_state(tmp_path)
 with pytest.raises(paper.PaperSnapshotBlocked) as failure:paper.PaperLedger.export(target)
 if kind in ('sidecar_link','dangling_sidecar','wal','shm','journal'):assert failure.value.code=='PAPER_SNAPSHOT_SIDECARS_UNSUPPORTED'
 assert disk_state(tmp_path)==before


@pytest.mark.parametrize('kwargs',[{'limit':0},{'limit':True},{'limit':201},{'max_bytes':0},{'max_bytes':True},{'max_bytes':4194305},{'validation_seconds':0},{'validation_seconds':float('nan')}])
def test_export_rejects_bad_budgets_before_sqlite(tmp_path,kwargs):
 path,ledger,request,result=populated(tmp_path)
 with patch.object(paper.sqlite3,'connect',side_effect=AssertionError('MUST_NOT_OPEN')):
  with pytest.raises(paper.PaperSnapshotBlocked) as failure:ledger.snapshot(**kwargs)
 assert failure.value.code=='PAPER_SNAPSHOT_ARGUMENT'


def test_export_byte_budget_fails_whole_snapshot_without_partial_row(tmp_path):
 path,ledger,request,result=populated(tmp_path);before=disk_state(tmp_path)
 with pytest.raises(paper.PaperSnapshotBlocked) as failure:ledger.snapshot(max_bytes=100)
 assert failure.value.code=='PAPER_SNAPSHOT_TOO_LARGE' and disk_state(tmp_path)==before


def test_export_validation_budget_is_blocked_not_corruption(tmp_path):
 path,ledger,request,result=populated(tmp_path);before=disk_state(tmp_path)
 with patch.object(paper.time,'monotonic',side_effect=[0,20,20,20,20]):
  with pytest.raises(paper.PaperSnapshotBlocked) as failure:ledger.snapshot(validation_seconds=1)
 assert failure.value.code=='PAPER_SNAPSHOT_BUDGET' and disk_state(tmp_path)==before


def test_export_uses_readonly_query_only_consistent_transaction(tmp_path):
 path,ledger,request,result=populated(tmp_path);connect=sqlite3.connect;queries=[];connections=[]
 class AuditedConnection(sqlite3.Connection):
  def execute(self,sql,*args):queries.append(sql);return super().execute(sql,*args)
 def opened(*args,**kwargs):
  assert kwargs.get('uri') is True and '?mode=ro' in str(args[0])
  kwargs['factory']=AuditedConnection;connection=connect(*args,**kwargs);connections.append(connection);return connection
 with patch.object(paper.sqlite3,'connect',side_effect=opened):paper.PaperLedger.export(path)
 assert 'PRAGMA query_only=ON' in queries and 'BEGIN' in queries
 assert not any(q.startswith(('INSERT','UPDATE','DELETE','CREATE','PRAGMA journal_mode')) for q in queries)
 with pytest.raises(sqlite3.ProgrammingError):connections[0].execute('SELECT 1')


def test_export_does_not_invoke_write_capable_constructor(tmp_path):
 path,ledger,request,result=populated(tmp_path)
 with patch.object(paper.PaperLedger,'__init__',side_effect=AssertionError('NO_CONSTRUCTOR')):
  assert paper.PaperLedger.export(path)['returned_count']==1


def test_bound_instance_and_static_export_reject_replaced_database(tmp_path):
 path,ledger,request,result=populated(tmp_path)
 replacement=tmp_path/'replacement.sqlite';replacement.write_bytes(path.read_bytes())
 os.replace(replacement,path)
 with pytest.raises(paper.PaperSnapshotBlocked):ledger.snapshot()
 # Static export also detects replacement between initial admission and open.
 replacement.write_bytes(path.read_bytes());connect=sqlite3.connect
 def changed(*args,**kwargs):os.replace(replacement,path);return connect(*args,**kwargs)
 with patch.object(paper.sqlite3,'connect',side_effect=changed):
  with pytest.raises(paper.PaperSnapshotBlocked):paper.PaperLedger.export(path)


def test_validation_deadline_after_real_evaluation_is_not_corruption(tmp_path):
 path,ledger,request,result=populated(tmp_path);before=disk_state(tmp_path);clock=[0.0];evaluate=paper.evaluate
 def slow(*args,**kwargs):
  result=evaluate(*args,**kwargs);clock[0]+=3;return result
 with patch.object(paper.time,'monotonic',side_effect=lambda:clock[0]),patch.object(paper,'evaluate',side_effect=slow):
  with pytest.raises(paper.PaperSnapshotBlocked) as failure:ledger.snapshot(validation_seconds=1)
 assert failure.value.code=='PAPER_SNAPSHOT_BUDGET' and disk_state(tmp_path)==before


def test_real_wal_is_blocked_without_checkpoint_or_shared_memory_mutation(tmp_path):
 path,ledger,request,result=populated(tmp_path)
 with sqlite3.connect(path) as writer:
  assert writer.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal'
  writer.execute('UPDATE trades SET admitted_ms=admitted_ms');writer.commit()
  assert Path(str(path)+'-wal').exists() and Path(str(path)+'-shm').exists()
  before=disk_state(tmp_path)
  with pytest.raises(paper.PaperSnapshotBlocked) as failure:paper.PaperLedger.export(path)
  assert failure.value.code=='PAPER_SNAPSHOT_SIDECARS_UNSUPPORTED'
  assert disk_state(tmp_path)==before


def test_invalid_export_path_is_a_typed_blocked_failure():
 with pytest.raises(paper.PaperSnapshotBlocked) as failure:paper.PaperLedger.export(None)
 assert failure.value.code=='PAPER_SNAPSHOT_ARGUMENT'


def test_checkpointed_wal_header_rejected_before_sqlite_can_create_sidecars(tmp_path):
 path,ledger,request,result=populated(tmp_path)
 writer=sqlite3.connect(path)
 try:
  assert writer.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal'
 finally:writer.close()
 assert not Path(str(path)+'-wal').exists() and not Path(str(path)+'-shm').exists()
 before=disk_state(tmp_path)
 with patch.object(paper.sqlite3,'connect',side_effect=AssertionError('MUST_NOT_OPEN_WAL')):
  with pytest.raises(paper.PaperSnapshotBlocked) as failure:paper.PaperLedger.export(path)
 assert failure.value.code=='PAPER_SNAPSHOT_WAL_UNSUPPORTED' and disk_state(tmp_path)==before


@pytest.mark.parametrize('raw',['relative.sqlite',r'\\not-a-local-host\share\ledger.sqlite','//not-a-local-host/share/ledger.sqlite'])
def test_nonlocal_or_relative_paths_reject_before_metadata(raw):
 with patch.object(Path,'lstat',side_effect=AssertionError('NO_NONLOCAL_METADATA')):
  with pytest.raises(paper.PaperSnapshotBlocked):paper.PaperLedger.export(raw)
