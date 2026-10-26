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
    explicit=os.environ.get('PG_BINDIR') or os.environ.get('STRATTESTER_TEST_PG_BIN')
    if explicit or os.environ.get('CI'):
        import psycopg
    else:
        psycopg=pytest.importorskip('psycopg')
    candidates=[Path(explicit)] if explicit else [Path('C:/Program Files/PostgreSQL/18/bin'),*sorted(Path('/usr/lib/postgresql').glob('*/bin'),reverse=True)]
    suffix='.exe' if os.name=='nt' else ''
    binary=next((p for p in candidates if (p/('initdb'+suffix)).is_file()),None)
    if binary is None:
        if explicit or os.environ.get('CI'):pytest.fail('required PostgreSQL fixture binaries unavailable')
        pytest.skip('optional local PostgreSQL fixture binaries unavailable')
    version=subprocess.run([str(binary/('postgres'+suffix)),'--version'],check=True,capture_output=True,text=True,timeout=5).stdout.strip()
    assert version.startswith('postgres (PostgreSQL) ')
    data=tmp_path/'pg-owned';log=tmp_path/'pg-owned.log'
    subprocess.run([str(binary/('initdb'+suffix)),'-D',str(data),'-A','trust','-U','fixture','--no-locale','--encoding=UTF8'],check=True,capture_output=True,timeout=30)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    assert port!=5432
    with log.open('wb') as stream:
        process=subprocess.Popen([str(binary/('postgres'+suffix)),'-D',str(data),'-p',str(port),'-h','127.0.0.1','-c','max_connections=8'],stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
        dsn=f'host=127.0.0.1 port={port} dbname=postgres user=fixture connect_timeout=1'
        try:
            for attempt in range(100):
                if process.poll() is not None:pytest.fail(log.read_text())
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
            subprocess.run([str(binary/('pg_ctl'+suffix)),'-D',str(data),'-m','immediate','-w','stop'],capture_output=True,timeout=15)
            process.wait(timeout=15)


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
