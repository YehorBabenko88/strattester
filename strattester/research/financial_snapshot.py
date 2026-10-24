"""Bounded snapshot bytes and read-only normalized SQLite ingestion.

No production schemas, epochs, knowledge timestamps or quality are synthesized.
"""
from dataclasses import asdict, fields
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import stat
from .financial_contract import Instrument, Bar, Snapshot, digest, integer


def canonical_bytes(payload):
    return json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('duplicate JSON key')
        result[key]=value
    return result


def reject_linked_path(path):
    """Reject existing symlink/reparse components; not native race confinement.

    Keep the lexical path: resolving first hides ancestor junctions. Native
    handle-relative confinement is still required against hostile concurrent
    namespace changes on Windows (and for SQLite's separate open).
    """
    path=Path(path)
    if ".." in path.parts:
        raise ValueError("parent traversal artifact path rejected")
    path=Path(os.path.abspath(path))
    for component in (*reversed(path.parents),path):
        info=component.lstat()
        if (stat.S_ISLNK(info.st_mode)
            or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)):
            raise ValueError('symlink/reparse artifact path rejected')
    return path


def verified_bytes(path, expected_sha256, max_bytes):
    digest(expected_sha256); integer(max_bytes,'max_bytes',1)
    path=reject_linked_path(path)
    if path.is_symlink() or not path.is_file(): raise ValueError('ordinary non-symlink artifact required')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if info.st_nlink!=1: raise ValueError('artifact hardlink identity rejected')
        if not stat.S_ISREG(info.st_mode) or info.st_size>max_bytes: raise ValueError('artifact size/type budget')
        data=stream.read(max_bytes+1)
        after=os.fstat(stream.fileno())
        reject_linked_path(path)
        current=path.lstat()
        if (after.st_nlink!=1 or (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
            or (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino) or path.is_symlink()):
            raise ValueError('artifact identity changed during read')
    if len(data)>max_bytes: raise ValueError('artifact byte budget')
    if sha256(data).hexdigest()!=expected_sha256: raise ValueError('artifact SHA256 mismatch')
    return data


def bounded_json(data):
    # Scan nesting before the parser can recursively allocate arbitrary objects.
    depth=0; quoted=False; escaped=False
    for byte in data:
        if quoted:
            if escaped: escaped=False
            elif byte==92: escaped=True
            elif byte==34: quoted=False
        elif byte==34: quoted=True
        elif byte in (91,123):
            depth+=1
            if depth>64: raise ValueError('JSON nesting budget')
        elif byte in (93,125): depth-=1
    def invalid_constant(value): raise ValueError('nonfinite JSON constant')
    try: payload=json.loads(data,object_pairs_hook=unique_object,parse_constant=invalid_constant)
    except (RecursionError,UnicodeError) as exc: raise ValueError('invalid bounded JSON') from exc
    if type(payload) is not dict: raise ValueError('JSON object required')
    return payload


def snapshot_bytes(snapshot):
    snapshot.validate()
    return canonical_bytes({'version':1,**asdict(snapshot)})


def load_snapshot(path, expected_sha256, *, trusted_producers, expected_coherence, max_bytes=8*1024*1024):
    data=verified_bytes(path,expected_sha256,max_bytes)
    payload=bounded_json(data)
    if set(payload)!={'version','bars','origin_ns','coherence_id','producers'} or type(payload['version']) is not int or payload['version']!=1:
        raise ValueError('BLOCKED: snapshot schema')
    if not expected_coherence or payload['coherence_id']!=expected_coherence:
        raise ValueError('BLOCKED: untrusted coherence identity')
    if not set(payload['producers']).issubset(trusted_producers): raise ValueError('BLOCKED: untrusted producer')
    bars=[]
    for row in payload['bars']:
        item=dict(row)
        item['instrument']=Instrument(**item['instrument'])
        bars.append(Bar(**item))
    return Snapshot(tuple(bars),payload['origin_ns'],payload['coherence_id'],tuple(payload['producers'])).validate()


def read_sqlite_bars(path, *, origin_ns, max_rows=100_000):
    """Yield one transaction of normalized rows, not a multi-source attestation.

    Only the explicitly versioned research_bars schema is supported. Caller
    must separately bind rows to a trusted coherent export before model use.
    """
    integer(origin_ns,'origin'); integer(max_rows,'max_rows',1)
    path=reject_linked_path(path)
    if path.is_symlink() or not path.is_file(): raise ValueError('existing ordinary SQLite file required')
    con=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,isolation_level=None,timeout=1)
    con.row_factory=sqlite3.Row
    try:
        con.execute('PRAGMA query_only=ON'); con.execute('PRAGMA trusted_schema=OFF'); con.execute('BEGIN')
        names={r[1] for r in con.execute('PRAGMA table_info(research_bars)')}
        expected={f.name for f in fields(Bar)}-{'instrument'}|{f.name for f in fields(Instrument)}
        if names!=expected: raise ValueError('BLOCKED: unsupported source schema; availability/provenance cannot be inferred')
        # Include future rows in validation rather than silently returning a
        # partial "complete" dataset when the input artifact is noncausal.
        for count,row in enumerate(con.execute('SELECT * FROM research_bars ORDER BY exchange,market_type,symbol,timeframe_ns,candle_open_ns')):
            if count>=max_rows: raise ValueError('row budget exceeded; partial read is not a Snapshot')
            item=dict(row)
            identity={key:item.pop(key) for key in ('exchange','market_type','symbol')}
            for key in ('eligible','complete'):
                if type(item[key]) is not int or item[key] not in (0,1): raise ValueError('invalid SQLite boolean')
                item[key]=bool(item[key])
            bar=Bar(instrument=Instrument(**identity),**item)
            bar.validate(origin_ns)
            yield bar
        con.execute('COMMIT')
    finally:
        if con.in_transaction: con.execute('ROLLBACK')
        con.close()
