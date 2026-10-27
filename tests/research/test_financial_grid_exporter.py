from dataclasses import asdict, replace
from hashlib import sha256
import json
import sqlite3
import pytest
from strattester.research.financial_contract import Bar, Instrument
from strattester.research.financial_snapshot import canonical_bytes, load_snapshot
from strattester.research.financial_signed_export import MarketPartition
from strattester.research.financial_grid_exporter import *


def fixture(tmp_path, name='one', epoch='epoch', symbol='BTCUSDT'):
    path=tmp_path/(name+'.db');p=MarketPartition('bybit','linear',symbol,10)
    bar=Bar(Instrument('bybit','linear',symbol),10,0,10,9,10,10,30,100.,'VERIFIED',True,True,1,'producer','a'*40)
    rows=[{'bar':asdict(bar),'first_available_ns':10,'source_id':name,'coherence_epoch_id':epoch},
          {'bar':asdict(replace(bar,available_ns=40,revision=2,close=200.,watermark_ns=40)),'first_available_ns':10,'source_id':name,'coherence_epoch_id':epoch}]
    meta=dict(source_id=name,snapshot_id='cut-'+name,coherence_epoch_id=epoch,schema_sha256=SCHEMA_SHA256,complete=True,first_availability_retained=True,revision_history_retained=True,event_watermark_ns=30,availability_watermark_ns=30,partitions=[asdict(p)])
    with sqlite3.connect(path) as con:
        con.execute('PRAGMA journal_mode=WAL')
        for ddl in DDL: con.execute(ddl)
        con.execute('INSERT INTO history_meta VALUES (?)',(canonical_bytes(meta).decode(),))
        con.executemany('INSERT INTO history_rows VALUES (?)',[(canonical_bytes(r).decode(),) for r in rows])
    source=HistorySource(name,'sqlite',str(path),'cut-'+name,history_seal(meta,rows),(p,))
    return source, rows, meta


def run(profile,path,**kwargs):
    return export_history(profile,path,producer_id='producer',producer_build_sha='a'*40,key_id='key',export_id='export',issued_at_ns=31,**kwargs)


def isolate_postgres_fixture_environment(monkeypatch):
    """Keep the explicit test binary pin; isolate this owned fixture's libpq."""
    import os
    explicit=os.environ.get('PG_BINDIR') or os.environ.get('STRATTESTER_TEST_PG_BIN')
    for name in tuple(os.environ):
        if name.upper().startswith('PG') and name.upper()!='PG_BINDIR':
            monkeypatch.delenv(name)
    return explicit


def owned_postgres_fixture_root(tmp_path):
    """Grant only a fresh hosted-Windows fixture child to the current user SID.

    PostgreSQL drops Administrators privileges; Python 3.13 pytest ancestors
    can then be inaccessible. Do not repair pytest, workspace or runner ACLs.
    Upstream rationale: postgres/.github/workflows/pg-ci.yml Windows ACL step.
    Hosted operational flags select fixture setup, never G1 authorization.
    """
    import csv
    import io
    import os
    import re
    import subprocess
    import sys
    import tempfile
    from strattester.research.financial_snapshot import reject_linked_path
    if (sys.platform!='win32' or os.environ.get('GITHUB_ACTIONS')!='true'
        or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted'
        or os.environ.get('RUNNER_OS')!='Windows'):
        return tmp_path
    runner=Path(os.environ.get('RUNNER_TEMP',''))
    if not runner.is_absolute():raise ValueError('absolute RUNNER_TEMP required')
    runner=reject_linked_path(runner)
    if not runner.is_dir():raise ValueError('RUNNER_TEMP directory required')
    windows=Path(os.environ.get('SystemRoot',''))
    if not windows.is_absolute():raise ValueError('absolute SystemRoot required')
    windows=reject_linked_path(windows)
    identified=subprocess.run([str(windows/'System32'/'whoami.exe'),'/user','/fo','csv','/nh'],capture_output=True,text=True,timeout=10)
    identified.check_returncode()
    rows=list(csv.reader(io.StringIO(identified.stdout)))
    if (len(rows)!=1 or len(rows[0])!=2
        or re.fullmatch(r'S-1-5-21-(?:[0-9]{1,10}-){3}[0-9]{1,10}',rows[0][1]) is None):
        raise ValueError('one current-user SID required')
    sid=rows[0][1]
    owned=reject_linked_path(tempfile.mkdtemp(prefix='strattester-pg-',dir=runner))
    if owned.parent!=runner or not owned.name.startswith('strattester-pg-') or not owned.is_dir():
        raise ValueError('new owned child required for ACL grant')
    granted=subprocess.run([str(windows/'System32'/'icacls.exe'),str(owned),'/grant',f'*{sid}:(OI)(CI)F','/Q'],capture_output=True,text=True,timeout=10)
    granted.check_returncode()
    # Preserve this owned fixture for diagnostics; never recursively delete it
    # or change any ancestor's ACL. Hosted runner disposal owns final cleanup.
    return owned


def mock_hosted_postgres_root(tmp_path,monkeypatch,*,sid_csv='"runneradmin","S-1-5-21-123-456-789-1001"\n',failed_tool=None):
    import subprocess
    import sys
    runner=tmp_path/'runner-temp';runner.mkdir()
    windows=tmp_path/'windows';windows.mkdir()
    monkeypatch.setattr(sys,'platform','win32')
    for name,value in {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Windows','RUNNER_TEMP':str(runner),'SystemRoot':str(windows)}.items():
        monkeypatch.setenv(name,value)
    calls=[]
    def command(argv,**kwargs):
        calls.append(argv)
        assert kwargs.get('shell',False) is False
        assert kwargs['timeout']==10
        tool=Path(argv[0]).name
        assert tool in ('whoami.exe','icacls.exe')
        return subprocess.CompletedProcess(argv,int(tool==failed_tool),sid_csv if tool=='whoami.exe' else '', 'intentional failure' if tool==failed_tool else '')
    monkeypatch.setattr(subprocess,'run',command)
    return runner,windows,calls


def test_hosted_postgres_root_grants_only_new_unique_child_to_current_user_sid(tmp_path,monkeypatch):
    runner,windows,calls=mock_hosted_postgres_root(tmp_path,monkeypatch)
    first=owned_postgres_fixture_root(tmp_path);second=owned_postgres_fixture_root(tmp_path)
    assert first!=second and first.parent==second.parent==runner
    assert first.is_dir() and second.is_dir()
    assert calls==[
        [str(windows/'System32'/'whoami.exe'),'/user','/fo','csv','/nh'],
        [str(windows/'System32'/'icacls.exe'),str(first),'/grant','*S-1-5-21-123-456-789-1001:(OI)(CI)F','/Q'],
        [str(windows/'System32'/'whoami.exe'),'/user','/fo','csv','/nh'],
        [str(windows/'System32'/'icacls.exe'),str(second),'/grant','*S-1-5-21-123-456-789-1001:(OI)(CI)F','/Q']]


@pytest.mark.parametrize('platform,github,runner,runner_os',[
    ('linux','true','github-hosted','Linux'),('win32','false','github-hosted','Windows'),
    ('win32','true','self-hosted','Windows'),('win32','true','github-hosted','Linux')])
def test_nonhosted_postgres_root_never_changes_acl(tmp_path,monkeypatch,platform,github,runner,runner_os):
    import subprocess
    import sys
    monkeypatch.setattr(sys,'platform',platform)
    for name,value in {'GITHUB_ACTIONS':github,'RUNNER_ENVIRONMENT':runner,'RUNNER_OS':runner_os}.items():monkeypatch.setenv(name,value)
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:pytest.fail('nonhosted ACL command attempted'))
    assert owned_postgres_fixture_root(tmp_path)==tmp_path


@pytest.mark.parametrize('sid_csv',['"runner","S-1-5-32-544"\n','"runner","not-a-sid"\n','"runner","S-1-5-21-1-2-3-4"\n"other","S-1-5-21-1-2-3-5"\n'],ids=['group-sid','malformed','multiple'])
def test_hosted_postgres_root_rejects_nonuser_or_ambiguous_sid(tmp_path,monkeypatch,sid_csv):
    runner,windows,calls=mock_hosted_postgres_root(tmp_path,monkeypatch,sid_csv=sid_csv)
    with pytest.raises(ValueError,match='SID'):owned_postgres_fixture_root(tmp_path)
    assert all(Path(argv[0]).name=='whoami.exe' for argv in calls)
    assert list(runner.iterdir())==[]


@pytest.mark.parametrize('failed_tool',['whoami.exe','icacls.exe'])
def test_hosted_postgres_root_rejects_failed_identity_or_acl_command(tmp_path,monkeypatch,failed_tool):
    import subprocess
    mock_hosted_postgres_root(tmp_path,monkeypatch,failed_tool=failed_tool)
    with pytest.raises(subprocess.CalledProcessError):owned_postgres_fixture_root(tmp_path)


def test_hosted_postgres_root_rejects_parent_as_acl_target(tmp_path,monkeypatch):
    import tempfile
    runner,windows,calls=mock_hosted_postgres_root(tmp_path,monkeypatch)
    monkeypatch.setattr(tempfile,'mkdtemp',lambda **kwargs:str(runner))
    with pytest.raises(ValueError,match='owned child'):owned_postgres_fixture_root(tmp_path)
    assert all(Path(argv[0]).name=='whoami.exe' for argv in calls)


@pytest.mark.parametrize('binary_variable',['PG_BINDIR','STRATTESTER_TEST_PG_BIN'])
def test_owned_postgres_fixture_clears_ambient_libpq_but_preserves_binary_pin(monkeypatch,binary_variable):
    import os
    monkeypatch.delenv('PG_BINDIR',raising=False)
    monkeypatch.delenv('STRATTESTER_TEST_PG_BIN',raising=False)
    monkeypatch.setenv(binary_variable,'owned-fixture-bin')
    for name in ('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGSERVICE','PGROOT','PGDATA'):
        monkeypatch.setenv(name,'ambient-test-value')
    monkeypatch.setenv('UNRELATED_FIXTURE_SETTING','preserved')
    assert isolate_postgres_fixture_environment(monkeypatch)=='owned-fixture-bin'
    assert not [name for name in os.environ if name.upper().startswith('PG') and name.upper()!='PG_BINDIR']
    assert os.environ[binary_variable]=='owned-fixture-bin'
    assert os.environ['UNRELATED_FIXTURE_SETTING']=='preserved'


def stop_owned_postgres(binary,data,suffix,process=None,*,primary_error=None):
    """Stop only the fixture's explicit data directory; never manage a service."""
    import subprocess
    failures=[]
    try:
        stopped=subprocess.run([str(binary/('pg_ctl'+suffix)),'-D',str(data),'-m','immediate','-w','stop'],capture_output=True,timeout=15)
        stopped.check_returncode()
    except (OSError,subprocess.SubprocessError) as error:
        failures.append(error)
    if process is not None:
        try:process.wait(timeout=15)
        except (OSError,subprocess.SubprocessError) as error:failures.append(error)
    if failures:
        # A failed setup/test already fails the gate; preserve that exception
        # while making unsuccessful cleanup visible, including shutdown timeout.
        failure=primary_error if primary_error is not None else failures[0]
        for error in failures:
            failure.add_note('owned PostgreSQL shutdown failed: '+str(error))
        if primary_error is None:raise failure


@pytest.mark.parametrize('failure',['exit','timeout'])
def test_owned_postgres_shutdown_failure_cannot_pass(tmp_path,monkeypatch,failure):
    import subprocess
    def failed_stop(command,**kwargs):
        if failure=='timeout':raise subprocess.TimeoutExpired(command,kwargs['timeout'])
        return subprocess.CompletedProcess(command,1,b'',b'could not stop server')
    monkeypatch.setattr(subprocess,'run',failed_stop)
    with pytest.raises(subprocess.SubprocessError):
        stop_owned_postgres(tmp_path/'bin',tmp_path/'pg-owned','.exe')


@pytest.mark.parametrize('failure',['exit','timeout'])
def test_owned_postgres_shutdown_preserves_original_startup_failure(tmp_path,monkeypatch,failure):
    import subprocess
    import sys
    def failed_stop(command,**kwargs):
        if failure=='timeout':raise subprocess.TimeoutExpired(command,kwargs['timeout'])
        return subprocess.CompletedProcess(command,1,b'',b'shutdown failed')
    monkeypatch.setattr(subprocess,'run',failed_stop)
    primary=RuntimeError('original startup failure')
    with pytest.raises(RuntimeError,match='original startup failure') as observed:
        try:raise primary
        finally:stop_owned_postgres(tmp_path/'bin',tmp_path/'pg-owned','.exe',primary_error=sys.exception())
    assert observed.value is primary
    assert any('owned PostgreSQL shutdown failed' in note for note in getattr(primary,'__notes__',()))


def test_owned_postgres_shutdown_is_scoped_and_waits_for_direct_child(tmp_path,monkeypatch):
    import subprocess
    calls=[]
    def stopped(command,**kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command,0,b'',b'')
    class Child:
        waited=False
        def wait(self,timeout):
            assert timeout==15
            self.waited=True
    child=Child();monkeypatch.setattr(subprocess,'run',stopped)
    stop_owned_postgres(tmp_path/'bin',tmp_path/'pg-owned','.exe',child)
    assert calls==[[str(tmp_path/'bin'/'pg_ctl.exe'),'-D',str(tmp_path/'pg-owned'),'-m','immediate','-w','stop']]
    assert child.waited


def test_complete_sealed_history_replays_and_emits_consumer_schema(tmp_path):
    source,_,_=fixture(tmp_path)
    result=run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'output')
    assert result.snapshot.bars[0].close==100
    loaded=load_snapshot(result.directory/'snapshot.json',result.snapshot_sha256,trusted_producers={'producer'},expected_coherence='epoch')
    assert loaded==result.snapshot
    manifest=json.loads((result.directory/'unsigned-manifest.json').read_bytes())
    assert manifest['sources'][0]['first_availability_retained'] is True
    assert manifest['sources'][0]['engine']=='sqlite'
    assert 'signature_b64' not in manifest
    assert json.loads((result.directory/'provenance.json').read_bytes())['sources'][0]['raw_logical_sha256']==source.seal_sha256


def test_native_blocks_before_path_access(tmp_path,monkeypatch):
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:pytest.fail('database accessed'))
    with pytest.raises(RuntimeError,match='native Grid export BLOCKED'):
        run(HistoryProfile('NATIVE_GRID','epoch',30,()),tmp_path/'output')


def test_equal_cutoffs_do_not_establish_epoch(tmp_path):
    a,_,_=fixture(tmp_path);b,_,_=fixture(tmp_path,'two','different','ETHUSDT')
    with pytest.raises(ValueError,match='epoch/seal'):
        run(HistoryProfile(PROFILE,'epoch',30,(a,b)),tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_concurrent_wal_revision_invalidates_external_seal(tmp_path):
    source,rows,_=fixture(tmp_path)
    with sqlite3.connect(source.location) as writer:
        changed=rows[0]|{'bar':rows[0]['bar']|{'close':999.}}
        writer.execute('UPDATE history_rows SET payload=? WHERE rowid=1',(canonical_bytes(changed).decode(),))
    with pytest.raises(ValueError,match='seal changed'):
        run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'output')


@pytest.mark.parametrize('failure',['history','schema','budget','cancel'])
def test_fail_closed_no_partial_artifacts(tmp_path,failure):
    source,rows,meta=fixture(tmp_path)
    if failure=='history':
        rows[0]['first_available_ns']=11
        with sqlite3.connect(source.location) as con:con.execute('UPDATE history_rows SET payload=? WHERE rowid=1',(canonical_bytes(rows[0]).decode(),))
        source=replace(source,seal_sha256=history_seal(meta,rows))
    if failure=='schema':
        with sqlite3.connect(source.location) as con:con.execute('CREATE TABLE extra (x TEXT)')
    kwargs={'max_rows':1} if failure=='budget' else {'cancel':lambda:True} if failure=='cancel' else {}
    with pytest.raises((ValueError,RuntimeError)):
        run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'output',**kwargs)
    assert not (tmp_path/'output').exists()
    assert not list(tmp_path.glob('.history-export-*'))


def test_shards_require_disjoint_routing_and_all_seals(tmp_path):
    a,_,_=fixture(tmp_path);b,_,_=fixture(tmp_path,'two','epoch','ETHUSDT')
    result=run(HistoryProfile(PROFILE,'epoch',30,(replace(a,engine='sharded_sqlite'),replace(b,engine='sharded_sqlite'))),tmp_path/'output')
    assert len(result.snapshot.bars)==2


def test_disposable_postgres_mvcc_and_seals(tmp_path, monkeypatch):
    """Own a child PostgreSQL cluster, never inspect/start/stop installed services."""
    import os
    import socket
    import subprocess
    import time
    from contextlib import contextmanager
    import strattester.research.financial_grid_exporter as module
    explicit=isolate_postgres_fixture_environment(monkeypatch)
    if explicit or os.environ.get('CI'):
        import psycopg
    else:
        psycopg=pytest.importorskip('psycopg')
    candidates=[Path(explicit)] if explicit else [*sorted(Path('C:/Program Files/PostgreSQL').glob('*/bin'),reverse=True),*sorted(Path('/usr/lib/postgresql').glob('*/bin'),reverse=True)]
    suffix='.exe' if os.name=='nt' else ''
    binary=next((p for p in candidates if (p/('initdb'+suffix)).is_file()),None)
    if binary is None:
        if explicit or os.environ.get('CI'):pytest.fail('required PostgreSQL fixture binaries unavailable')
        pytest.skip('optional local PostgreSQL fixture binaries unavailable')
    version=subprocess.run([str(binary/('postgres'+suffix)),'--version'],check=True,capture_output=True,text=True,timeout=5).stdout.strip()
    assert version.startswith('postgres (PostgreSQL) ')
    pg_root=owned_postgres_fixture_root(tmp_path)
    data=pg_root/'pg-owned';log=pg_root/'pg-owned.log'
    initialized=subprocess.run([str(binary/('initdb'+suffix)),'-D',str(data),'-A','trust','-U','fixture','--no-locale','--encoding=UTF8'],capture_output=True,text=True,timeout=30)
    assert initialized.returncode==0,initialized.stdout+initialized.stderr
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    assert port!=5432
    with log.open('wb') as stream:
        # Own TCP-only fixture: never use the installed cluster's shared Unix
        # socket directory (e.g. /var/run/postgresql on hosted Linux).
        process=None if os.name=='nt' else subprocess.Popen([str(binary/('postgres'+suffix)),'-D',str(data),'-p',str(port),'-h','127.0.0.1','-c','max_connections=8','-c','unix_socket_directories='],stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
        dsn=f'host=127.0.0.1 port={port} dbname=postgres user=fixture connect_timeout=1'
        try:
            if os.name=='nt':
                stream.close() # pg_ctl owns the log; no conflicting CRT handle.
                # pg_ctl itself drops administrative privileges on Windows;
                # direct postgres.exe intentionally refuses an elevated runner.
                # A background postmaster can retain inherited pipe handles:
                # use a task-owned regular log, never communicate() on pipes.
                control_log=pg_root/'pg-control.log'
                with control_log.open('wb') as control:
                    started=subprocess.run([str(binary/'pg_ctl.exe'),'-D',str(data),'-l',str(log),'-o',f'-p {port} -h 127.0.0.1 -c max_connections=8 -c unix_socket_directories=', '-w','-t','20','start'],stdout=control,stderr=subprocess.STDOUT,timeout=30)
                assert started.returncode==0,control_log.read_text()+log.read_text()
            for attempt in range(100):
                if process is not None and process.poll() is not None:pytest.fail(log.read_text())
                try:
                    with psycopg.connect(dsn):pass
                    break
                except psycopg.OperationalError:time.sleep(.05)
            else:pytest.fail('owned postgres startup timeout')
            source,rows,meta=fixture(tmp_path)
            with psycopg.connect(dsn) as con:
                for ddl in DDL:con.execute(ddl)
                con.execute('INSERT INTO history_meta VALUES (%s)',(canonical_bytes(meta).decode(),))
                for row in rows:con.execute('INSERT INTO history_rows VALUES (%s)',(canonical_bytes(row).decode(),))
            source=replace(source,engine='postgresql',location=dsn)
            original=module._reader
            # Exercise transfer bounds directly, independently of the exporter's
            # already-bounded same-MVCC count/byte preflight.
            with psycopg.connect(dsn) as writer:
                with writer.cursor() as cursor:cursor.executemany('INSERT INTO history_rows VALUES (%s)',[('{}',)]*1024)
            with original(source,lambda:False) as execute:
                cursor=execute('SELECT payload FROM history_rows LIMIT 1027')
                assert getattr(cursor,'name',None), 'history transfer must use named server cursor'
                assert cursor.itersize==1
                observed=0
                for transferred in cursor:
                    observed+=1
                    assert cursor.pgresult is None or cursor.pgresult.ntuples<=1
                assert observed==1026
            with psycopg.connect(dsn) as writer:writer.execute("DELETE FROM history_rows WHERE payload='{}'")
            @contextmanager
            def concurrent_reader(s,check,**limits):
                with original(s,check,**limits) as execute:
                    assert execute('SHOW transaction_isolation').fetchone()[0]=='repeatable read'
                    assert execute('SHOW transaction_read_only').fetchone()[0]=='on'
                    execute('SELECT payload FROM history_meta').fetchone() # establish MVCC snapshot
                    with psycopg.connect(dsn) as writer:
                        changed=rows[0]|{'bar':rows[0]['bar']|{'close':999.}}
                        writer.execute('UPDATE history_rows SET payload=%s WHERE payload=%s',(canonical_bytes(changed).decode(),canonical_bytes(rows[0]).decode()))
                    yield execute
            monkeypatch.setattr(module,'_reader',concurrent_reader)
            result=run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'mvcc')
            assert result.snapshot.bars[0].close==100. # consistent old, externally sealed view
            monkeypatch.setattr(module,'_reader',original)
            with pytest.raises(ValueError,match='seal changed'):
                run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'changed')
        finally:
            # Stop precisely this owned cluster using its explicit data directory.
            import sys
            stop_owned_postgres(binary,data,suffix,process,primary_error=sys.exception())


def test_public_rfc_signer_replays_through_pinned_consumer(tmp_path):
    import base64
    import shutil
    from strattester.research.financial_signatures import OpenSSLVerifier
    from strattester.research.financial_signed_export import ExportPolicy,SourceIdentity,load_attested_export
    source,rows,meta=fixture(tmp_path)
    for row in rows:row['bar']['producer']='fixture-grid'
    with sqlite3.connect(source.location) as con:
        con.execute('DELETE FROM history_rows')
        con.executemany('INSERT INTO history_rows VALUES (?)',[(canonical_bytes(row).decode(),) for row in rows])
    source=replace(source,seal_sha256=history_seal(meta,rows))
    artifacts=export_history(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'export',producer_id='fixture-grid',producer_build_sha='a'*40,key_id='rfc-key',export_id='test',issued_at_ns=31)
    exe=Path(shutil.which('openssl') or 'C:/Program Files/Git/usr/bin/openssl.exe').resolve()
    if not exe.is_file():pytest.skip('OpenSSL test binary unavailable')
    exe_sha=sha256(exe.read_bytes()).hexdigest()
    manifest,manifest_sha=sign_rfc_test_export(artifacts,openssl_executable=exe,openssl_sha256=exe_sha,scratch_root=tmp_path)
    trust=canonical_bytes(dict(version=1,keys=[dict(producer_id='fixture-grid',key_id='rfc-key',public_key_b64=base64.b64encode(bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')).decode(),valid_from_ns=0,valid_until_ns=100,revoked=False)]))
    (tmp_path/'trust.json').write_bytes(trust)
    result=load_attested_export(manifest_path=manifest,manifest_sha256=manifest_sha,snapshot_path=artifacts.directory/'snapshot.json',trust_store_path=tmp_path/'trust.json',trust_store_sha256=sha256(trust).hexdigest(),policy=ExportPolicy('fixture-grid','epoch',30,(SourceIdentity('one','sqlite',SCHEMA_SHA256),),source.partitions,verification_ns=32),verifier=OpenSSLVerifier(exe,exe_sha,tmp_path))
    assert result.snapshot==artifacts.snapshot
    assert (manifest.parent/'signature.ed25519').stat().st_size==64
    assert sign_rfc_test_export(artifacts,openssl_executable=exe,openssl_sha256=exe_sha,scratch_root=tmp_path)==(manifest,manifest_sha)


def test_sqlite_wal_concurrent_writer_keeps_sealed_read_view(tmp_path,monkeypatch):
    import strattester.research.financial_grid_exporter as module
    from contextlib import contextmanager
    source,rows,_=fixture(tmp_path)
    original=module._reader
    @contextmanager
    def concurrent_reader(s,check,**limits):
        with original(s,check,**limits) as execute:
            assert execute('PRAGMA query_only').fetchone()[0]==1
            execute('SELECT payload FROM history_meta').fetchone()
            with sqlite3.connect(s.location) as writer:
                writer.execute('UPDATE history_rows SET payload=? WHERE rowid=1',(canonical_bytes(rows[0]|{'bar':rows[0]['bar']|{'close':999.}}).decode(),))
            yield execute
    monkeypatch.setattr(module,'_reader',concurrent_reader)
    assert run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'view').snapshot.bars[0].close==100.
    monkeypatch.setattr(module,'_reader',original)
    with pytest.raises(ValueError,match='seal changed'):
        run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'changed')


def test_failed_atomic_publication_preserves_stage_and_cleanup_inventory(tmp_path,monkeypatch):
    import strattester.research.financial_grid_exporter as module
    source,_,_=fixture(tmp_path)
    def fail(*args):raise OSError('publication failure')
    monkeypatch.setattr(module.os,'rename',fail)
    with pytest.raises(OSError,match='publication failure'):
        run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'output')
    assert not (tmp_path/'output').exists()
    stages=[p for p in tmp_path.glob('.history-export-*') if p.is_dir()]
    assert len(stages)==1
    cleanup=json.loads((tmp_path/(stages[0].name+'.cleanup.json')).read_bytes())
    assert cleanup['automatic_cleanup'] is False
    assert cleanup['state']=='INCOMPLETE_EXPORT_STAGE'


def test_retry_recovers_completed_export_after_child_loses_return_value(tmp_path):
    import os
    import subprocess
    import sys
    source,_,_=fixture(tmp_path)
    profile=HistoryProfile(PROFILE,'epoch',30,(source,))
    target=tmp_path/'completed'
    code='from strattester.research.financial_grid_exporter import *; import os; '+f'export_history({profile!r},{str(target)!r},producer_id="producer",producer_build_sha="'+('a'*40)+'",key_id="key",export_id="export",issued_at_ns=31); os._exit(17)'
    child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
    assert child.returncode==17, child.stderr
    before={p.name:p.read_bytes() for p in target.iterdir()}
    recovered=run(profile,target)
    assert recovered.snapshot.bars[0].close==100.
    assert {p.name:p.read_bytes() for p in target.iterdir()}==before


@pytest.mark.parametrize('kind',['partial','conflicting','extra','changed-source'])
def test_retry_rejects_partial_conflicting_or_unsealed_existing_output(tmp_path,kind):
    source,rows,_=fixture(tmp_path)
    profile=HistoryProfile(PROFILE,'epoch',30,(source,));target=tmp_path/'output'
    run(profile,target)
    if kind=='partial':(target/'provenance.json').unlink()
    elif kind=='conflicting':
        (target/'snapshot.json').write_bytes(b'{}')
        manifest=json.loads((target/'unsigned-manifest.json').read_bytes())
        manifest.update(snapshot_sha256=sha256(b'{}').hexdigest(),snapshot_bytes=2)
        (target/'unsigned-manifest.json').write_bytes(canonical_bytes(manifest))
        provenance=json.loads((target/'provenance.json').read_bytes())
        provenance['snapshot_sha256']=sha256(b'{}').hexdigest()
        (target/'provenance.json').write_bytes(canonical_bytes(provenance))
    elif kind=='extra':(target/'extra.json').write_bytes(b'{}')
    else:
        with sqlite3.connect(source.location) as con:con.execute('UPDATE history_rows SET payload=? WHERE rowid=1',(canonical_bytes(rows[0]|{'bar':rows[0]['bar']|{'close':999.}}).decode(),))
    before={p.name:p.read_bytes() for p in target.iterdir()}
    with pytest.raises(ValueError):run(profile,target)
    assert {p.name:p.read_bytes() for p in target.iterdir()}==before


@pytest.mark.parametrize('conflict',['signature','extra','partial'])
def test_export_sign_export_retry_and_sign_retry_keep_base_immutable(tmp_path,conflict):
    import shutil
    source,rows,meta=fixture(tmp_path)
    for row in rows:row['bar']['producer']='fixture-grid'
    with sqlite3.connect(source.location) as con:
        con.execute('DELETE FROM history_rows')
        con.executemany('INSERT INTO history_rows VALUES (?)',[(canonical_bytes(row).decode(),) for row in rows])
    source=replace(source,seal_sha256=history_seal(meta,rows))
    profile=HistoryProfile(PROFILE,'epoch',30,(source,))
    def export():return export_history(profile,tmp_path/'export',producer_id='fixture-grid',producer_build_sha='a'*40,key_id='rfc-key',export_id='test',issued_at_ns=31)
    exe=Path(shutil.which('openssl') or 'C:/Program Files/Git/usr/bin/openssl.exe').resolve()
    if not exe.is_file():pytest.skip('OpenSSL test binary unavailable')
    arguments=dict(openssl_executable=exe,openssl_sha256=sha256(exe.read_bytes()).hexdigest(),scratch_root=tmp_path)
    artifacts=export();before={p.name:p.read_bytes() for p in artifacts.directory.iterdir()}
    first=sign_rfc_test_export(artifacts,**arguments)
    assert first[0].parent==tmp_path/'export.signed-test'
    assert {p.name:p.read_bytes() for p in artifacts.directory.iterdir()}==before
    recovered=export()
    assert sign_rfc_test_export(recovered,**arguments)==first
    if conflict=='signature':(first[0].parent/'signature.ed25519').write_bytes(b'bad')
    elif conflict=='extra':(first[0].parent/'extra.json').write_bytes(b'{}')
    else:(first[0].parent/'signature.ed25519').unlink()
    conflicting_before={p.name:p.read_bytes() for p in first[0].parent.iterdir()}
    with pytest.raises(ValueError):sign_rfc_test_export(recovered,**arguments)
    assert {p.name:p.read_bytes() for p in first[0].parent.iterdir()}==conflicting_before


def test_sqlite_helper_rejects_oversized_cell_before_python_decode(tmp_path):
    import strattester.research.financial_grid_exporter as module
    source,_,_=fixture(tmp_path)
    with sqlite3.connect(source.location) as con:
        con.execute('DELETE FROM history_rows')
        con.execute('INSERT INTO history_rows VALUES (?)',('x'*(8*1024*1024+1),))
    # Direct helper probe: public export already rejects this at aggregate
    # preflight. The connection-level cap is an additional independent boundary.
    with module._reader(source,lambda:False) as execute:
        with pytest.raises(sqlite3.DataError,match='too big'):
            execute('SELECT payload FROM history_rows LIMIT 1').fetchone()


def test_utf8_octet_budget_rejects_history_before_json_parsing(tmp_path,monkeypatch):
    import strattester.research.financial_grid_exporter as module
    source,rows,meta=fixture(tmp_path,symbol='💰'*100)
    payloads=[json.dumps(row,ensure_ascii=False) for row in rows]
    with sqlite3.connect(source.location) as con:
        con.execute('UPDATE history_meta SET payload=?',(json.dumps(meta,ensure_ascii=False),))
        con.execute('DELETE FROM history_rows')
        con.executemany('INSERT INTO history_rows VALUES (?)',[(text,) for text in payloads])
    parsed=[];original=module.bounded_json
    def parse(data):
        parsed.append(data)
        return original(data)
    monkeypatch.setattr(module,'bounded_json',parse)
    with pytest.raises(ValueError,match='raw history allocation budget'):
        run(HistoryProfile(PROFILE,'epoch',30,(source,)),tmp_path/'output',max_bytes=sum(map(len,payloads)))
    assert len(parsed)==1 # metadata only; raw history rejected by octet preflight


@pytest.mark.parametrize('dsn,ambient',[('dbname=postgres',None),('host=127.0.0.1 port=45678 dbname=postgres user=fixture','PGHOST'),('host=127.0.0.1 port=45678 dbname=postgres user=fixture','PGPASSWORD'),('host=127.0.0.1 port=45678 dbname=postgres user=fixture service=hidden',None),('host=127.0.0.1 port=45678 dbname=postgres user=fixture options=hidden',None)])
def test_postgres_config_rejects_hidden_defaults_before_connect(tmp_path,monkeypatch,dsn,ambient):
    import os
    import psycopg
    import strattester.research.financial_grid_exporter as module
    for name in tuple(os.environ):
        if name.upper().startswith('PG') and name!='PG_BINDIR':monkeypatch.delenv(name)
    if ambient:monkeypatch.setenv(ambient,'must-not-be-logged')
    monkeypatch.setattr(psycopg,'connect',lambda *a,**k:pytest.fail('physical connect reached'))
    source=HistorySource('source','postgresql',dsn,'cut','a'*64,(MarketPartition('bybit','linear','BTCUSDT',10),))
    with pytest.raises(ValueError) as failure:
        with module._reader(source,lambda:False):pass
    assert 'must-not-be-logged' not in str(failure.value)


def test_postgres_explicit_endpoint_pins_credential_free_connect_policy(tmp_path,monkeypatch):
    import os
    import psycopg
    import strattester.research.financial_grid_exporter as module
    for name in tuple(os.environ):
        if name.upper().startswith('PG') and name.upper()!='PG_BINDIR':monkeypatch.delenv(name)
    monkeypatch.setenv('PG_BINDIR','test-metadata-only')
    captured={}
    def connect(*args,**kwargs):
        assert not args
        captured.update(kwargs)
        raise RuntimeError('intentional connection boundary stop')
    monkeypatch.setattr(psycopg,'connect',connect)
    source=HistorySource('source','postgresql','host=127.0.0.1 port=45678 dbname=postgres user=fixture','cut','a'*64,(MarketPartition('bybit','linear','BTCUSDT',10),))
    with pytest.raises(RuntimeError,match='intentional connection boundary stop'):
        with module._reader(source,lambda:False):pass
    assert captured==dict(host='127.0.0.1',port='45678',dbname='postgres',user='fixture',connect_timeout=3,passfile=os.devnull,password='',sslmode='disable',gssencmode='disable',require_auth='none',autocommit=True)
