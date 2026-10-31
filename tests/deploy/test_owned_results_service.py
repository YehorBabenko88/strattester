"""Read-only owner adapter: actual stores and HTTP, no research authority."""
import http.client
import json
from pathlib import Path
import sqlite3
import threading

import pytest

TOKEN='a'*64
IDENTITY=('strattester','1.0.0','cloud-fixture',TOKEN)


def adapter():
    from strattester import owned_results_service
    return owned_results_service


@pytest.fixture
def store(tmp_path):
    from strattester.persistence.result_store import ResultStore
    path=tmp_path/'results.db';result=ResultStore.open(path)
    result.con.execute('PRAGMA wal_checkpoint(TRUNCATE)');result.close()
    return path


def call(app,path='/internal/v2/module/health',auth='Bearer '+TOKEN,query=''):
    output=[]
    env={'PATH_INFO':path,'QUERY_STRING':query,'REQUEST_METHOD':'GET','owned.authorization':[] if auth is None else [auth]}
    body=b''.join(app(env,lambda status,headers:output.append((status,headers))))
    return int(output[0][0].split()[0]),json.loads(body)


def test_prepare_has_no_store_or_socket_effects(tmp_path):
    missing=tmp_path/'must-not-create.db'
    assert adapter().main(['--store',str(missing)])==0
    assert not missing.exists()


def test_actual_store_schema_probe_and_exact_health(store):
    before=store.read_bytes();app=adapter().OwnedResultsApp(store,IDENTITY)
    status,body=call(app)
    assert status==200 and body==dict(module_id='strattester',version='1.0.0',release_id='cloud-fixture',instance_token=TOKEN,ready=True)
    assert store.read_bytes()==before


@pytest.mark.parametrize('authorization',[None,'Bearer '+'b'*64,'bearer '+TOKEN])
def test_health_and_results_require_exact_nonce(store,authorization):
    app=adapter().OwnedResultsApp(store,IDENTITY)
    for path in ('/internal/v2/module/health','/internal/v1/capabilities'):
        status,body=call(app,path,authorization)
        assert status==403 and TOKEN not in json.dumps(body)


def test_missing_or_wrong_schema_fails_without_creating_store(tmp_path):
    missing=tmp_path/'missing.db'
    assert call(adapter().OwnedResultsApp(missing,IDENTITY))[0]==503
    assert not missing.exists()
    con=sqlite3.connect(missing);con.execute('CREATE TABLE research_results(fake)');con.close()
    assert call(adapter().OwnedResultsApp(missing,IDENTITY))[0]==503


def test_query_denied_and_existing_result_api_preserved(store):
    app=adapter().OwnedResultsApp(store,IDENTITY)
    assert call(app,query='x=1')[0]==400
    status,body=call(app,'/internal/v1/capabilities')
    assert status==200 and body['read_only'] is True and body['capabilities']['runs'] is False
    assert call(app,'/internal/v1/runs')[0]==503


def test_live_wal_schema_is_visible_without_checkpoint(tmp_path):
    from strattester.persistence.result_store import ResultStore
    result=ResultStore.open(tmp_path/'live.db')
    try:
        assert (result.path.with_name('live.db-wal')).stat().st_size>0
        assert call(adapter().OwnedResultsApp(result.path,IDENTITY))[0]==200
    finally:result.close()


def test_real_loopback_http_duplicate_auth_and_post_denied(store):
    service=adapter();server=service.make_server(service.OwnedResultsApp(store,IDENTITY),0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
        client.putrequest('GET','/internal/v2/module/health');client.putheader('Authorization','Bearer '+TOKEN);client.putheader('Authorization','Bearer '+TOKEN);client.endheaders()
        response=client.getresponse();assert response.status==403;response.read();client.close()
        client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
        client.request('POST','/internal/v1/runs',headers={'Authorization':'Bearer '+TOKEN})
        response=client.getresponse();assert response.status==405;response.read();client.close()
    finally:server.shutdown();server.server_close();thread.join(2)


def test_view_cannot_impersonate_result_store_tables(tmp_path):
    path=tmp_path/'views.db';con=sqlite3.connect(path)
    con.execute('CREATE VIEW research_results AS SELECT 1 run_id,1 symbol,1 strategy_id,1 strategy_version,1 created_at,1 metrics,1 job_id,1 lease_token,1 node_generation')
    con.execute('CREATE VIEW owned_runs AS SELECT 1 run_id,1 state,1 record');con.close()
    assert call(adapter().OwnedResultsApp(path,IDENTITY))[0]==503


def test_raw_bootstrap_real_source_pins_and_dirty_source_rejection(tmp_path,monkeypatch,store):
    import os
    import subprocess
    import sys
    unified=Path(os.environ.get('STRATTESTER_TEST_UNIFIED_ROOT',os.environ.get('UNIFIED_SOURCE_ROOT',str(Path(__file__).resolve().parents[3]/'unified-system'))))
    # CI checks out this exact shared dependency; no alternate verifier exists.
    assert (unified/'integration/source_guard.py').is_file(), 'trusted Unified dependency checkout is required'
    root=tmp_path/'trusted-root';own=tmp_path/'strattester';cache=tmp_path/'private-cache'
    root.mkdir();own.mkdir();cache.mkdir(mode=0o700)
    for target,files in ((root,('integration/source_guard.py','unified_system/owned_python.py')),(own,('strattester/__init__.py','strattester/owned_results_service.py','strattester/readonly_api.py','strattester/research/__init__.py','strattester/research/financial_executable_inventory.py','strattester/research/financial_contract.py','strattester/research/financial_snapshot.py'))):
        origin=unified if target==root else Path(__file__).resolve().parents[2]
        for name in files:
            destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes((origin/name).read_bytes())
        def git(*args):return subprocess.check_output(['git','-C',str(target),*args],text=True).strip()
        git('init','-q');git('add','.')
        git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','source')
    def head(target):return subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(UNIFIED_SOURCE_ROOT=str(root),UNIFIED_SOURCE_COMMIT=head(own),UNIFIED_ROOT_SOURCE_COMMIT=head(root),UNIFIED_PRIVATE_CACHE_ROOT=str(cache))
    for key,value in zip(('UNIFIED_MODULE_ID','UNIFIED_MODULE_VERSION','UNIFIED_RELEASE_ID','UNIFIED_INSTANCE_TOKEN'),IDENTITY):env[key]=value
    command=[sys.executable,'-I','-S','-B',str(root/'unified_system/owned_python.py'),'--source-root',str(own),'--dependency-root',str(root),'--module','strattester.owned_results_service','--','--verify-source']
    assert subprocess.run(command,env=env,capture_output=True,timeout=20).returncode!=0
    import hashlib
    import shutil
    executable=str(Path(shutil.which('git')).resolve())
    env.update(UNIFIED_GIT_EXECUTABLE=executable,UNIFIED_GIT_SHA256=hashlib.sha256(Path(executable).read_bytes()).hexdigest())
    result=subprocess.run(command,env=env,capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr.decode()
    env['UNIFIED_SOURCE_COMMIT']='b'*40
    assert subprocess.run(command,env=env,capture_output=True,timeout=20).returncode!=0
    env['UNIFIED_SOURCE_COMMIT']=head(own)
    original=(own/'strattester/__init__.py').read_bytes()
    (own/'strattester/__init__.py').write_text('__version__="forged"\n')
    assert subprocess.run(command,env=env,capture_output=True,timeout=20).returncode!=0
    (own/'strattester/__init__.py').write_bytes(original)
    actual_digest=env['UNIFIED_GIT_SHA256'];env['UNIFIED_GIT_SHA256']='0'*64
    assert subprocess.run(command,env=env,capture_output=True,timeout=20).returncode!=0
    env['UNIFIED_GIT_SHA256']=actual_digest
    import socket
    import time
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    before=store.read_bytes()
    process=subprocess.Popen(command[:-1]+['--serve','--store',str(store),'--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+10
        while True:
            if process.poll() is not None:pytest.fail(process.stderr.read().decode())
            client=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
            try:
                client.request('GET','/internal/v2/module/health',headers={'Authorization':'Bearer '+TOKEN})
                response=client.getresponse();body=json.loads(response.read())
                if response.status==200:break
            except ConnectionError:pass
            finally:client.close()
            assert time.monotonic()<deadline
            time.sleep(.05)
        assert body['ready'] is True and body['module_id']=='strattester'
        client=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
        client.request('GET','/internal/v1/runs');response=client.getresponse()
        assert response.status==403;response.read();client.close()
        removed=store.with_suffix('.unavailable');store.rename(removed)
        try:
            client=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
            client.request('GET','/internal/v2/module/health',headers={'Authorization':'Bearer '+TOKEN})
            response=client.getresponse();assert response.status==503 and json.loads(response.read())['ready'] is False;client.close()
        finally:removed.rename(store)
    finally:
        process.terminate();process.wait(timeout=3);process.stderr.close()
    assert store.read_bytes()==before
    assert not list(own.rglob('*.pyc')) and not list(root.rglob('*.pyc'))


def test_existing_producer_owned_receipt_survives_transport(store,tmp_path):
    from strattester.marketdata.sqlite_store import Candle,SQLiteMarketStore
    from strattester.persistence.result_store import ResultStore
    from strattester.research.runner import ResearchRunner
    from strattester.strategies.base import DataRequirement,StrategyDefinition
    class Sum:
        def run(self,candles,checkpoint=None):return {'sum':sum(c.close for c in candles)}
    market=SQLiteMarketStore.open(tmp_path/'market.db');results=ResultStore.open(store)
    try:
        market.upsert_candles([Candle('BTCUSDT','1m',t,1,2,1,2,1) for t in (0,60000)])
        ResearchRunner(market,object(),clock_ms=lambda:999999).run(
            StrategyDefinition('receipt-sum','1',(DataRequirement('candles',('1m',)),),Sum),
            {'symbol':'BTCUSDT','launchTime':'0'},start_ms=0,end_ms=60000,result_store=results,
            provenance=dict(source_identity='synthetic:fixture',market_type='linear',producer_identity='synthetic:owner',source_revision='a'*40,
                model={'kind':'synthetic','version':'1'},execution_assumptions={'fees':0,'slippage':0,'execution':'none'}))
        record=json.loads(results.con.execute("SELECT record FROM owned_runs WHERE state='COMPLETE'").fetchone()[0])
        app=adapter().OwnedResultsApp(store,IDENTITY,
            trusted_sources=[(record['producer_identity'],record['source_revision'],record['dataset']['source_identity'])],
            trusted_receipts=[(record['producer_identity'],record['source_revision'],record['run_id'],record['completion_receipt'])])
        status,body=call(app,'/internal/v1/runs')
        assert status==200 and body['runs']==[record] and body['execution_authority'] is False
        assert body['physical_attestation']=='UNVERIFIED'
    finally:results.close();market.close()


def test_source_verifier_timeout_stops_owned_process_tree(tmp_path,monkeypatch):
    import os
    import subprocess
    import time
    service=adapter();root=tmp_path/'trusted-root';(root/'unified_system').mkdir(parents=True)
    marker=tmp_path/'heartbeat'
    child="import pathlib,time; p=pathlib.Path("+repr(str(marker))+");\nwhile True: p.write_text(str(time.time())); time.sleep(.03)"
    script="import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',"+repr(child)+"])\ntime.sleep(60)\n"
    (root/'unified_system/owned_python.py').write_text(script)
    monkeypatch.setenv('UNIFIED_SOURCE_ROOT',str(root));monkeypatch.setattr(service,'SOURCE_VERIFY_TIMEOUT',.3,raising=False)
    start=time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):service.verify_source_bounded()
    assert time.monotonic()-start<3
    before=marker.read_bytes() if marker.exists() else b''
    time.sleep(.15)
    assert (marker.read_bytes() if marker.exists() else b'')==before


def test_slow_header_cannot_hold_single_private_listener(store):
    import socket
    import time
    service=adapter();server=service.make_server(service.OwnedResultsApp(store,IDENTITY),0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=socket.create_connection(('127.0.0.1',server.server_port),timeout=2)
    try:
        client.sendall(b'GET /internal/v2/module/health HTTP/1.0\r\nHost: localhost\r\nX-Slow: ')
        start=time.monotonic();closed=False
        while time.monotonic()-start<1:
            try:client.sendall(b'a')
            except (BrokenPipeError,ConnectionResetError):closed=True;break
            time.sleep(.08)
        assert closed and time.monotonic()-start<.9
    finally:client.close();server.shutdown();server.server_close();thread.join(2)


def test_wal_link_rejected_before_exists_or_target_probe(store,tmp_path,monkeypatch):
    target=tmp_path/'outside-target';target.write_bytes(b'not a WAL')
    wal=store.with_name(store.name+'-wal')
    try:wal.symlink_to(target)
    except OSError:pytest.skip('symlink creation unavailable')
    original_exists=Path.exists;original_lstat=Path.lstat;observed=[]
    def exists(path):
        if path==wal:raise AssertionError('exists follows untrusted WAL target')
        return original_exists(path)
    def lstat(path,*args,**kwargs):
        if path==target:raise AssertionError('external target metadata probed')
        if path==wal:observed.append('wal-lstat')
        return original_lstat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'exists',exists);monkeypatch.setattr(Path,'lstat',lstat)
    assert call(adapter().OwnedResultsApp(store,IDENTITY))[0]==503
    assert observed


def test_windows_tree_cleanup_uses_explicit_system_binary(monkeypatch):
    import subprocess
    from types import SimpleNamespace
    service=adapter();calls=[]
    monkeypatch.setenv('SystemRoot',r'C:\Windows')
    monkeypatch.setattr(subprocess,'run',lambda command,**kwargs:calls.append(command) or SimpleNamespace(returncode=0))
    service.terminate_windows_tree(1234)
    assert calls==[[r'C:\Windows\System32\taskkill.exe','/PID','1234','/T','/F']]


def test_existing_readonly_health_metadata_sees_live_wal_tables(tmp_path):
    from strattester.persistence.result_store import ResultStore
    from strattester.readonly_api import ReadOnlyResultsApp
    result=ResultStore.open(tmp_path/'live.db')
    try:assert ReadOnlyResultsApp(result.path)._source_reason()=='SOURCE_PROVENANCE_UNQUALIFIED'
    finally:result.close()


def test_existing_qualified_api_does_not_probe_wal_link(store,tmp_path,monkeypatch):
    from strattester.readonly_api import ReadOnlyResultsApp
    target=tmp_path/'outside';target.write_bytes(b'not a WAL');wal=store.with_name(store.name+'-wal')
    try:wal.symlink_to(target)
    except OSError:pytest.skip('symlink creation unavailable')
    original=Path.exists
    def exists(path):
        if path==wal:raise AssertionError('exists probes linked WAL before validation')
        return original(path)
    monkeypatch.setattr(Path,'exists',exists)
    records,reason=ReadOnlyResultsApp(store,trusted_sources=[('a','b','c')])._qualified('/internal/v1/runs',{})
    assert records is None and reason


@pytest.mark.parametrize('root',[r'C:\Windows\..\elsewhere',r'C:\Windows:stream',r'\\host\Windows'])
def test_windows_cleanup_rejects_noncanonical_system_root(monkeypatch,root):
    import subprocess
    service=adapter();monkeypatch.setenv('SystemRoot',root)
    monkeypatch.setattr(subprocess,'run',lambda *args,**kwargs:pytest.fail('unsafe cleanup binary launched'))
    with pytest.raises(ValueError):service.terminate_windows_tree(1234)
