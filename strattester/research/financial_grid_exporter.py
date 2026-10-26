"""Read-only exporter for externally sealed, versioned research history.

Native Grid's latest-state schema is deliberately unsupported. A profile is a
trusted external seal, not evidence manufactured by the exporter or database.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import tempfile
from .financial_contract import Bar, Instrument, Snapshot, digest, integer
from .financial_snapshot import bounded_json, canonical_bytes, reject_linked_path, snapshot_bytes, verified_bytes
from .financial_signed_export import MarketPartition, SNAPSHOT_SCHEMA_SHA256, identity
from .grid_producer_readiness import require_native_grid_export

PROFILE = 'SEALED_VERSIONED_HISTORY_V1'
DDL = ('CREATE TABLE history_meta (payload TEXT NOT NULL)',
       'CREATE TABLE history_rows (payload TEXT NOT NULL)')
SCHEMA_SHA256 = sha256(canonical_bytes(list(DDL))).hexdigest()

@dataclass(frozen=True)
class HistorySource:
    source_id: str
    engine: str
    location: str
    snapshot_id: str
    seal_sha256: str
    partitions: tuple[MarketPartition, ...]

@dataclass(frozen=True)
class HistoryProfile:
    kind: str
    coherence_epoch_id: str
    knowledge_cutoff_ns: int
    sources: tuple[HistorySource, ...]
    scope: str = 'SYNTHETIC_ENGINEERING_ONLY'

@dataclass(frozen=True)
class ExportArtifacts:
    snapshot: Snapshot
    directory: Path
    snapshot_sha256: str
    unsigned_manifest_sha256: str
    provenance_sha256: str



def _preserve_owned_stage(stage, target, reason):
    """Leave task data intact and record a non-authoritative cleanup inventory.

    No recursive deletion is attempted: a path can change after a confinement
    check. The marker lives beside the stage, so a replaced stage is not opened.
    """
    marker=stage.parent/(stage.name+'.cleanup.json')
    try:
        reject_linked_path(stage.parent)
        with marker.open('xb') as stream:
            stream.write(canonical_bytes({'version':1,'state':reason,
                'stage_path':str(stage.absolute()),'intended_target':str(target.absolute()),
                'automatic_cleanup':False,'recovery':'RECOMPUTE_FROM_TRUSTED_SEALED_SOURCES'}))
            stream.flush();os.fsync(stream.fileno())
    except (OSError,ValueError):
        pass  # Preserve the original export error; never delete to hide it.


def history_seal(meta, rows):
    """Canonical raw logical content seal; caller must provision it independently."""
    return sha256(canonical_bytes({'meta': meta, 'rows': sorted(rows, key=canonical_bytes)})).hexdigest()



def _explicit_postgres_parameters(location):
    """Accept one explicit credential-free endpoint; never discover libpq defaults."""
    import re
    from psycopg.conninfo import conninfo_to_dict
    if any(name.upper().startswith('PG') and name.upper()!='PG_BINDIR' for name in os.environ):
        raise ValueError('ambient libpq configuration rejected')
    if type(location) is not str or not 1<=len(location)<=4096:
        raise ValueError('explicit PostgreSQL configuration required')
    try: parameters=conninfo_to_dict(location)
    except Exception:raise ValueError('invalid explicit PostgreSQL configuration') from None
    required={'host','port','dbname','user'}
    if not required.issubset(parameters) or set(parameters)-required-{'connect_timeout'}:
        raise ValueError('explicit PostgreSQL endpoint required; discovery/credential parameters forbidden')
    if (not re.fullmatch(r'[A-Za-z0-9.:-]{1,256}',parameters['host'])
        or not parameters['port'].isdigit() or not 1<=int(parameters['port'])<=65535
        or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',parameters[k]) for k in ('dbname','user'))):
        raise ValueError('invalid explicit PostgreSQL endpoint')
    timeout=parameters.get('connect_timeout','3')
    if not timeout.isdigit() or not 1<=int(timeout)<=3:raise ValueError('PostgreSQL connection timeout policy')
    # This prototype supports credential-free research/fixture authentication.
    # A production TLS/credential policy requires a separately reviewed profile.
    return {**parameters,'connect_timeout':int(timeout),'passfile':os.devnull,
            'password':'','sslmode':'disable','gssencmode':'disable','require_auth':'none'}


@contextmanager
def _reader(source, check, *, max_bytes=8*1024*1024):
    if source.engine in ('sqlite', 'sharded_sqlite'):
        path = reject_linked_path(source.location)
        con = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, isolation_level=None, timeout=1)
        try:
            con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,max_bytes)
            con.execute('PRAGMA query_only=ON')
            con.execute('PRAGMA trusted_schema=OFF')
            def progress():
                try: return int(check())
                except Exception: return 1
            con.set_progress_handler(progress, 1000)
            con.execute('BEGIN')
            schema = tuple(r[0] for r in con.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 3"))
            if schema != DDL: raise ValueError('BLOCKED: physical schema identity')
            yield con.execute
        except sqlite3.OperationalError:
            check()
            raise
        finally:
            if con.in_transaction: con.rollback()
            con.close()
    elif source.engine == 'postgresql':
        # No service management or fallback discovery. Only the explicit DSN is used.
        import psycopg
        parameters=_explicit_postgres_parameters(source.location)
        with psycopg.connect(**parameters,autocommit=True) as con:
            con.execute('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            try:
                con.execute("SET LOCAL statement_timeout = '5000ms'")
                columns = con.execute("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position LIMIT 3").fetchall()
                if columns != [('history_meta','payload','text','NO'), ('history_rows','payload','text','NO')]:
                    raise ValueError('BLOCKED: physical schema identity')
                cursors=[]
                def execute(query):
                    if query.startswith('SELECT payload FROM history_rows') or (query.startswith('SELECT CASE WHEN') and ' FROM history_rows ' in query):
                        cursor=con.cursor(name='sealed_history_rows_'+str(len(cursors)))
                        cursors.append(cursor)
                        cursor.itersize=1;cursor.arraysize=1
                        cursor.execute(query)
                        return cursor
                    return con.execute(query)
                yield execute
            finally:
                for cursor in locals().get('cursors',[]):cursor.close()
                con.execute('ROLLBACK')
    else: raise ValueError('BLOCKED: unsupported source engine')


def export_history(profile, output_dir, *, producer_id, producer_build_sha,
                   key_id, export_id, issued_at_ns, max_rows=100_000,
                   max_bytes=8*1024*1024, cancel=lambda: False):
    """Publish one directory atomically; unsigned manifest requires trusted signing.

    Reads all retained revisions and verifies each source against externally
    pinned content seals. Equal cutoffs never establish cross-source coherence.
    No live physical database bytes are copied or hashed as an immutable backup.
    """
    if not isinstance(profile, HistoryProfile) or profile.kind != PROFILE:
        require_native_grid_export()  # Must precede any source/path access.
    from .financial_training import TrainingCancelled
    def check():
        if cancel(): raise TrainingCancelled('cancelled historical export')
        return False
    check()
    for v in (producer_id, key_id, export_id, profile.coherence_epoch_id): identity(v)
    digest(producer_build_sha,40)
    integer(profile.knowledge_cutoff_ns,'cutoff',1); integer(issued_at_ns,'issue',profile.knowledge_cutoff_ns)
    integer(max_rows,'row budget',1); integer(max_bytes,'byte budget',1)
    if max_rows>100_000 or max_bytes>8*1024*1024: raise ValueError('hard allocation budget')
    if profile.scope not in ('SYNTHETIC_ENGINEERING_ONLY','PRODUCER_ATTESTED_RESEARCH'): raise ValueError('scope')
    if type(profile.sources) is not tuple or not 1<=len(profile.sources)<=64 or len({s.source_id for s in profile.sources})!=len(profile.sources): raise ValueError('source membership')
    partitions=[]; bars=[]; receipts=[]; provenance=[]; total_rows=0; total_bytes=0
    for source in profile.sources:
        check();identity(source.source_id);identity(source.snapshot_id);digest(source.seal_sha256)
        if type(source) is not HistorySource or type(source.partitions) is not tuple or not 1<=len(source.partitions)<=256: raise ValueError('missing routing authority')
        for p in source.partitions: p.validate()
        partitions.extend(source.partitions)
        if len(partitions)>256: raise ValueError('partition membership budget')
        with _reader(source,check,max_bytes=max_bytes) as execute:
            size='octet_length(payload)' if source.engine=='postgresql' else 'length(CAST(payload AS BLOB))'
            if execute('SELECT count(*) FROM history_meta').fetchone()[0]!=1: raise ValueError('single epoch receipt required')
            meta_rows=execute(f'SELECT payload FROM history_meta WHERE {size}<={min(262144,max_bytes)} LIMIT 2').fetchmany(2)
            if len(meta_rows)!=1: raise ValueError('single epoch receipt required')
            meta=bounded_json(meta_rows[0][0].encode())
            expected={'source_id':source.source_id,'snapshot_id':source.snapshot_id,'coherence_epoch_id':profile.coherence_epoch_id,
                      'schema_sha256':SCHEMA_SHA256,'complete':True,'first_availability_retained':True,'revision_history_retained':True,
                      'event_watermark_ns':profile.knowledge_cutoff_ns,'availability_watermark_ns':profile.knowledge_cutoff_ns,
                      'partitions':[asdict(p) for p in source.partitions]}
            if any(type(meta.get(k)) is not bool for k in ('complete','first_availability_retained','revision_history_retained')): raise ValueError('historical receipt boolean type')
            # Python equality aliases JSON floats/bools to integer source facts.
            # Compare the canonical sealed representation before rebuilding receipts.
            if canonical_bytes(meta)!=canonical_bytes(expected): raise ValueError('BLOCKED: epoch/seal/completeness/routing facts')
            budget=execute(f'SELECT count(*),coalesce(sum({size}),0),coalesce(max({size}),0) FROM history_rows').fetchone()
            if budget[0]+total_rows>max_rows or budget[1]+total_bytes>max_bytes or budget[2]>max_bytes: raise ValueError('raw history allocation budget')
            rows=[]
            for row in execute(f'SELECT CASE WHEN {size}<={max_bytes-total_bytes} THEN payload ELSE NULL END AS payload FROM history_rows LIMIT {max_rows-total_rows+1}'):
                check()
                if row[0] is None:raise ValueError('raw history cell allocation budget')
                total_rows+=1;total_bytes+=len(row[0].encode())
                if total_rows>max_rows or total_bytes>max_bytes: raise ValueError('raw history allocation budget')
                rows.append(bounded_json(row[0].encode()))
            if history_seal(meta,rows)!=source.seal_sha256: raise ValueError('BLOCKED: historical seal changed')
        groups={}
        for raw in rows:
            check()
            if set(raw)!={'bar','first_available_ns','source_id','coherence_epoch_id'} or raw['source_id']!=source.source_id or raw['coherence_epoch_id']!=profile.coherence_epoch_id:
                raise ValueError('historical row identity')
            item=dict(raw['bar']);item['instrument']=Instrument(**item['instrument']);bar=Bar(**item)
            integer(raw['first_available_ns'],'first available',1)
            bar.validate(max(profile.knowledge_cutoff_ns,bar.available_ns,bar.watermark_ns))
            if bar.producer!=producer_id or bar.source_sha!=producer_build_sha: raise ValueError('producer provenance')
            p=MarketPartition(bar.instrument.exchange,bar.instrument.market_type,bar.instrument.symbol,bar.timeframe_ns)
            if p not in source.partitions: raise ValueError('shard routing mismatch')
            groups.setdefault((bar.instrument,bar.timeframe_ns,bar.candle_open_ns),[]).append((bar,raw['first_available_ns']))
        for versions in groups.values():
            check()
            versions.sort(key=lambda v:v[0].revision)
            first=versions[0][0].available_ns
            if [v[0].revision for v in versions]!=list(range(1,len(versions)+1)) or any(v[1]!=first for v in versions): raise ValueError('incomplete first availability/revision history')
            if any(a[0].available_ns>=b[0].available_ns for a,b in zip(versions,versions[1:])): raise ValueError('revision availability ordering')
            eligible=[v[0] for v in versions if v[0].available_ns<=profile.knowledge_cutoff_ns]
            if eligible: bars.append(eligible[-1])
        receipts.append({k:v for k,v in expected.items() if k!='partitions'} | {'engine':source.engine})
        provenance.append({'source_id':source.source_id,'snapshot_id':source.snapshot_id,'raw_logical_sha256':source.seal_sha256,'raw_rows':len(rows),'schema_sha256':SCHEMA_SHA256})
    if len(set(partitions))!=len(partitions): raise ValueError('overlapping shard routing')
    bars.sort(key=lambda b:(b.instrument,b.timeframe_ns,b.candle_open_ns))
    snapshot=Snapshot(tuple(bars),profile.knowledge_cutoff_ns,profile.coherence_epoch_id,(producer_id,)).validate()
    actual={MarketPartition(b.instrument.exchange,b.instrument.market_type,b.instrument.symbol,b.timeframe_ns) for b in bars}
    if actual!=set(partitions): raise ValueError('incomplete partition export')
    data=snapshot_bytes(snapshot)
    if len(data)>max_bytes: raise ValueError('snapshot byte budget')
    manifest=dict(version=1,producer_id=producer_id,producer_build_sha=producer_build_sha,key_id=key_id,export_id=export_id,
        coherence_epoch_id=profile.coherence_epoch_id,snapshot_schema_version=1,snapshot_schema_sha256=SNAPSHOT_SCHEMA_SHA256,
        snapshot_sha256=sha256(data).hexdigest(),snapshot_bytes=len(data),row_count=len(bars),knowledge_cutoff_ns=profile.knowledge_cutoff_ns,
        issued_at_ns=issued_at_ns,scope=profile.scope,partitions=[asdict(p) for p in partitions],sources=receipts)
    prov=canonical_bytes({'version':1,'profile':PROFILE,'sources':provenance,'snapshot_sha256':sha256(data).hexdigest(),
        'native_grid_truth':'NOT_ESTABLISHED','physical_g1':'NOT_AUTHORIZED','raw_hash_kind':'CANONICAL_LOGICAL_HISTORY_NOT_LIVE_DB_FILE'})
    manifest_data=canonical_bytes(manifest)
    check();target=Path(output_dir).absolute()
    reject_linked_path(target.parent)
    contents={'snapshot.json':data,'unsigned-manifest.json':manifest_data,'provenance.json':prov}
    result=ExportArtifacts(snapshot,target,sha256(data).hexdigest(),sha256(manifest_data).hexdigest(),sha256(prov).hexdigest())
    if target.exists() or target.is_symlink():
        reject_linked_path(target)
        if not target.is_dir() or {p.name for p in target.iterdir()}!=set(contents):
            raise ValueError('incomplete/conflicting publication membership')
        for name,expected in contents.items():
            check()
            actual=verified_bytes(target/name,sha256(expected).hexdigest(),len(expected))
            if actual!=expected:raise ValueError('conflicting publication bytes')
        check()
        return result
    temporary=Path(tempfile.mkdtemp(prefix='.history-export-',dir=target.parent))
    try:
        for name,content in contents.items():
            check()
            with (temporary/name).open('xb') as stream: stream.write(content);stream.flush();os.fsync(stream.fileno())
        check();os.rename(temporary,target)
    finally:
        if temporary.exists() or temporary.is_symlink():_preserve_owned_stage(temporary,target,'INCOMPLETE_EXPORT_STAGE')
    return result


def sign_rfc_test_export(artifacts, *, openssl_executable, openssl_sha256, scratch_root):
    """Sign SYNTHETIC fixture-grid/rfc-key only using a public RFC8032 test seed.

    This is deliberately unusable as a production key provisioner. Consumers
    still need their independently pinned verifier and explicit test trust store.
    Publishes a separate atomic signed-test directory; unsigned inputs stay fixed.
    """
    import base64
    import subprocess
    from .financial_snapshot import verified_bytes
    from .financial_signed_export import SIGNATURE_DOMAIN
    from .financial_signatures import OpenSSLVerifier
    public=bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
    seed=bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb')
    executable=Path(openssl_executable)
    if not executable.is_absolute(): raise ValueError('absolute pinned signer required')
    verified_bytes(executable,openssl_sha256,64*1024*1024)
    unsigned=bounded_json(verified_bytes(artifacts.directory/'unsigned-manifest.json',artifacts.unsigned_manifest_sha256,256*1024))
    if unsigned['scope']!='SYNTHETIC_ENGINEERING_ONLY' or unsigned['producer_id']!='fixture-grid' or unsigned['key_id']!='rfc-key':
        raise ValueError('public RFC signer restricted to fixture-grid/rfc-key synthetic engineering')
    verified_bytes(artifacts.directory/'snapshot.json',unsigned['snapshot_sha256'],8*1024*1024)
    scratch=reject_linked_path(scratch_root)
    base=reject_linked_path(artifacts.directory)
    if scratch==base or base in scratch.parents:raise ValueError('signing scratch must be outside immutable export')
    target=base.with_name(base.name+'.signed-test')
    reject_linked_path(target.parent)
    directory=tempfile.mkdtemp(prefix='rfc-test-sign-',dir=scratch)
    try:
        root=Path(directory)
        (root/'key.der').write_bytes(bytes.fromhex('302e020100300506032b657004220420')+seed)
        message=SIGNATURE_DOMAIN+canonical_bytes(unsigned)
        (root/'message').write_bytes(message);(root/'openssl.cnf').write_bytes(b'')
        env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR') if k in os.environ}
        env['OPENSSL_CONF']=str(root/'openssl.cnf')
        try:
            subprocess.run([str(executable),'pkeyutl','-sign','-rawin','-keyform','DER','-inkey',str(root/'key.der'),
                '-in',str(root/'message'),'-out',str(root/'signature')],cwd=root,env=env,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=True,shell=False)
        except (OSError,subprocess.SubprocessError) as exc: raise ValueError('test signing failed') from exc
        signature=(root/'signature').read_bytes()
        OpenSSLVerifier(executable,openssl_sha256,scratch).verify(public,message,signature)
        manifest=canonical_bytes(unsigned|{'signature_b64':base64.b64encode(signature).decode()})
        contents={'manifest.json':manifest,'signature.ed25519':signature}
        if target.exists() or target.is_symlink():
            reject_linked_path(target)
            if not target.is_dir() or {p.name for p in target.iterdir()}!=set(contents):
                raise ValueError('incomplete/conflicting test signature membership')
            for name,expected in contents.items():
                if verified_bytes(target/name,sha256(expected).hexdigest(),len(expected))!=expected:
                    raise ValueError('conflicting test signature bytes')
            return target/'manifest.json',sha256(manifest).hexdigest()
        stage=Path(tempfile.mkdtemp(prefix='.signed-test-',dir=target.parent))
        try:
            for name,data in contents.items():
                with (stage/name).open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.rename(stage,target)
        finally:
            if stage.exists() or stage.is_symlink():_preserve_owned_stage(stage,target,'INCOMPLETE_TEST_SIGNATURE_STAGE')
    finally:
        _preserve_owned_stage(Path(directory),target,'PUBLIC_RFC_TEST_SIGNING_SCRATCH')
    return target/'manifest.json',sha256(manifest).hexdigest()
