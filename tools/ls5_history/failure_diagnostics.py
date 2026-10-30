"""Bounded durable failure diagnostics. Never serialize exception messages/tracebacks."""
import json,os,time
from datetime import datetime,timezone
PHASES={'bootstrap','runtime_integrity','package_integrity','module_admission','network_initialization','server_time','universe_discovery','sqlite_initialization','candle_download','coverage_validation','rate_verification','publication','success_completion'}
CODES={'post_import_setup':'E2E_POST_IMPORT_FAILED','sqlite_initialization':'E2E_SQLITE_INITIALIZATION_FAILED','sqlite_seed':'E2E_SQLITE_SEED_FAILED','discovery':'E2E_DISCOVERY_FAILED','snapshot_verification':'E2E_SNAPSHOT_VERIFICATION_FAILED','publication':'E2E_PUBLICATION_FAILED','publication_hash':'E2E_PUBLICATION_HASH_FAILED'}
class Context:
 def __init__(self,run,nonce,source):
  self.run=run;self.nonce=nonce;self.source=source;self.pid=os.getpid();self.current='bootstrap';self.last=None;self.operation=None;self.start=time.monotonic()
 def phase(self,name):
  if name not in PHASES:raise ValueError('DIAGNOSTIC_PHASE_INVALID')
  self.current=name
 def durable(self,marker):self.last=dict(marker)
def safe_exception_type(exc):
 t=type(exc)
 if t.__module__=='builtins' and t.__name__ in {'ValueError','RuntimeError','AssertionError','OSError','PermissionError','FileNotFoundError','ImportError','ModuleNotFoundError','TypeError','KeyError','MemoryError'}:return t.__name__
 if t.__module__=='sqlite3' and t.__name__ in {'DatabaseError','OperationalError','IntegrityError','ProgrammingError','InterfaceError','DataError','NotSupportedError'}:return t.__name__
 return 'OtherException'
def capture_failure(ctx,exc):
 try:
  value=dict(schema='ls5.worker_failure.v1',status='WORKER_FAILED',phase=ctx.current,error_code=CODES.get(ctx.current,'E2E_'+ctx.current.upper()+'_FAILED'),exception_type=safe_exception_type(exc),pid=ctx.pid,nonce=ctx.nonce,source=ctx.source,last_durable_marker=ctx.last,timestamp_utc=datetime.now(timezone.utc).isoformat(),worker_exit_code=2,controller_exit_code=None,controller_exit_code_status='NOT_YET_KNOWN',cpu_seconds=time.process_time(),wall_seconds=time.monotonic()-ctx.start)
  data=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
  if len(data)>8192:return 3
  with (ctx.run/'failure.json').open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  return 2
 except Exception:return 3

def run_guarded(ctx,operation):
 try:operation();return 0
 except Exception as exc:return capture_failure(ctx,exc)
