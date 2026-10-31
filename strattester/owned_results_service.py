"""Explicit loopback transport for the existing read-only results boundary.

Prepare is inert. Serve must be launched by externally pinned owned_python.py.
No research, migration, scheduler, model promotion or execution is started here.
"""
import argparse
import json
import os
import ntpath
from pathlib import Path
import re
import secrets
import signal
import sqlite3
import subprocess
import sys
import time
import threading
import socket
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler


SOURCE_VERIFY_TIMEOUT=15


def identity():
    values=tuple(os.environ.get(k,'') for k in ('UNIFIED_MODULE_ID','UNIFIED_MODULE_VERSION','UNIFIED_RELEASE_ID','UNIFIED_INSTANCE_TOKEN'))
    if (values[0]!='strattester' or len(values[1])>128
        or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]{1,40})?',values[1])
        or not re.fullmatch('[A-Za-z0-9_.:-]{1,128}',values[2]) or not re.fullmatch('[a-f0-9]{64}',values[3])):
        raise ValueError('OWNED_PROFILE_UNAVAILABLE')
    return values


def check_source():
    """Reuse shared externally pinned Root policy; never authorize its own pin."""
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and sys.pycache_prefix):
        raise ValueError('OWNED_BOOTSTRAP_REQUIRED')
    root=Path(os.environ['UNIFIED_SOURCE_ROOT'])
    if not root.is_absolute():raise ValueError('SOURCE_UNAVAILABLE')
    for pin in ('UNIFIED_SOURCE_COMMIT','UNIFIED_ROOT_SOURCE_COMMIT'):
        if not re.fullmatch('[a-f0-9]{40}',os.environ.get(pin,'')):raise ValueError('SOURCE_UNAVAILABLE')
    executable=os.environ.get('UNIFIED_GIT_EXECUTABLE','')
    git_digest=os.environ.get('UNIFIED_GIT_SHA256','')
    if not executable or not re.fullmatch('[a-f0-9]{64}',git_digest):raise ValueError('GIT_PIN_UNAVAILABLE')
    sys.path.insert(0,str(root))
    from integration.source_guard import SourceFence
    if Path(sys.modules[SourceFence.__module__].__file__).resolve()!=root/'integration/source_guard.py':
        raise ValueError('SOURCE_UNAVAILABLE')
    for source,pin in ((root,os.environ['UNIFIED_ROOT_SOURCE_COMMIT']),
                       (Path(__file__).resolve().parents[1],os.environ['UNIFIED_SOURCE_COMMIT'])):
        fence=SourceFence(source,pin,isolated_cache=sys.pycache_prefix,git_executable=executable,git_sha256=git_digest);fence.check()
        if source!=root:fence.file(__file__,python=True)


def terminate_windows_tree(pid):
    root=os.environ.get('SystemRoot','')
    if not re.fullmatch(r'[A-Za-z]:[\\/][^\r\n]*',root) or '..' in root.replace('/','\\').split('\\') or ':' in root[2:]:
        raise ValueError('SYSTEM_CLEANUP_UNAVAILABLE')
    executable=ntpath.join(root,'System32','taskkill.exe')
    subprocess.run([executable,'/PID',str(pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)


def verify_source_bounded():
    root=Path(os.environ['UNIFIED_SOURCE_ROOT'])
    command=[sys.executable,'-I','-S','-B',str(root/'unified_system/owned_python.py'),
             '--source-root',str(Path(__file__).resolve().parents[1]),'--dependency-root',str(root),
             '--module','strattester.owned_results_service','--','--verify-source']
    kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
    child=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**kwargs)
    try:
        if child.wait(timeout=SOURCE_VERIFY_TIMEOUT)!=0:raise ValueError('SOURCE_UNAVAILABLE')
    except BaseException:
        if os.name!='nt':
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        else:
            terminate_windows_tree(child.pid)
        child.wait(timeout=3)
        raise


class OwnedResultsApp:
    def __init__(self,store,owned_identity,*,trusted_sources=(),trusted_receipts=()):
        from strattester.readonly_api import ReadOnlyResultsApp
        self.api=ReadOnlyResultsApp(store,trusted_sources=trusted_sources,trusted_receipts=trusted_receipts)
        self.identity=owned_identity

    def ready(self):
        try:
            con=sqlite3.connect(self.api._source_uri(),uri=True,timeout=.1)
            try:
                deadline=time.monotonic()+.1
                con.set_progress_handler(lambda:int(time.monotonic()>=deadline),100)
                con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
                for table in ('research_results','owned_runs'):
                    if con.execute('SELECT type FROM sqlite_master WHERE name=?',(table,)).fetchone()!=('table',):return False
                con.execute('SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token,node_generation FROM research_results LIMIT 0')
                con.execute('SELECT run_id,state,record FROM owned_runs LIMIT 0')
                return con.execute('SELECT 1').fetchone()==(1,) and time.monotonic()<deadline
            finally:con.close()
        except (OSError,ValueError,sqlite3.Error):return False

    def __call__(self,environ,start_response):
        headers=[('Content-Type','application/json'),('Cache-Control','no-store')]
        def reply(status,data):
            body=json.dumps(data,sort_keys=True,allow_nan=False).encode()
            start_response(str(status)+' '+{200:'OK',400:'Bad Request',403:'Forbidden',405:'Method Not Allowed',503:'Service Unavailable'}[status],headers+[('Content-Length',str(len(body)))])
            return [body]
        auth=environ.get('owned.authorization',[])
        if (len(auth)!=1 or len(auth[0])>256 or not secrets.compare_digest(auth[0].encode('utf-8'),('Bearer '+self.identity[3]).encode('ascii'))):
            return reply(403,{'error':'FORBIDDEN'})
        if environ.get('REQUEST_METHOD')!='GET':return reply(405,{'error':'READ_ONLY'})
        if environ.get('PATH_INFO')=='/internal/v2/module/health':
            if environ.get('QUERY_STRING'):return reply(400,{'error':'INVALID_QUERY'})
            ready=self.ready()
            return reply(200 if ready else 503,dict(zip(('module_id','version','release_id','instance_token'),self.identity),ready=ready))
        return self.api(environ,start_response)


class PrivateHandler(WSGIRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(.5)
    def log_message(self,*args):pass
    def get_environ(self):
        env=super().get_environ();env['owned.authorization']=self.headers.get_all('Authorization',[])
        return env
    def handle(self):
        def expire():
            try:self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        deadline=threading.Timer(.5,expire);deadline.start()
        try:super().handle()
        except (TimeoutError,ConnectionError):pass
        finally:deadline.cancel()


class PrivateServer(WSGIServer):
    request_queue_size=4
    allow_reuse_address=False


def make_server(app,port):
    server=PrivateServer(('127.0.0.1',port),PrivateHandler);server.set_app(app)
    return server


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve',action='store_true');parser.add_argument('--verify-source',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--store');parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args(argv)
    if args.verify_source:identity();check_source();return 0
    if not args.serve:
        print(json.dumps({'status':'PREPARE','listening':False,'read_only':True}));return 0
    owned=identity()
    if not args.store or not 1<=args.port<=65535:raise ValueError('SERVICE_CONFIGURATION_UNAVAILABLE')
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):raise ValueError('OWNED_BOOTSTRAP_REQUIRED')
    verify_source_bounded()
    raw=os.environ.get('STRATTESTER_RESULTS_TRUST_JSON','{"sources":[],"receipts":[]}')
    if len(raw)>16384:raise ValueError('TRUST_CONFIGURATION_UNAVAILABLE')
    trust=json.loads(raw)
    if set(trust)!={'sources','receipts'} or any(type(trust[k]) is not list or len(trust[k])>64 for k in trust):raise ValueError('TRUST_CONFIGURATION_UNAVAILABLE')
    for key,size in (('sources',3),('receipts',4)):
        if any(type(row) is not list or len(row)!=size or any(type(v) is not str or len(v)>256 for v in row) for row in trust[key]):raise ValueError('TRUST_CONFIGURATION_UNAVAILABLE')
    app=OwnedResultsApp(args.store,owned,trusted_sources=trust['sources'],trusted_receipts=trust['receipts'])
    if not app.ready():raise ValueError('RESULT_STORE_UNAVAILABLE')
    with make_server(app,args.port) as server:server.serve_forever(poll_interval=.2)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,subprocess.SubprocessError):
        print('OWNED_RESULTS_UNAVAILABLE',file=sys.stderr);raise SystemExit(1)
