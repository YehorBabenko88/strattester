import json
import sqlite3
from dataclasses import asdict
from hashlib import sha256
import pytest
from strattester.research.financial_contract import Instrument, Bar, Snapshot
from strattester.research.financial_snapshot import snapshot_bytes, load_snapshot, read_sqlite_bars


def fixture_snapshot():
    rows=tuple(Bar(Instrument('bybit','linear','BTCUSDT'),60,t,t+60,t+59,t+60,t+60,120,
                   100.+t,'VERIFIED',True,True,1,'producer','a'*40) for t in (0,60))
    return Snapshot(rows,120,'trusted-epoch',('producer',))


def test_verified_bytes_roundtrip_and_provenance_tamper(tmp_path):
    data=snapshot_bytes(fixture_snapshot())
    path=tmp_path/'snapshot.json'; path.write_bytes(data)
    digest=sha256(data).hexdigest()
    got=load_snapshot(path,digest,trusted_producers={'producer'},expected_coherence='trusted-epoch')
    assert got == fixture_snapshot()
    path.write_bytes(data.replace(b'100.0',b'101.0'))
    with pytest.raises(ValueError,match='SHA256'): load_snapshot(path,digest,trusted_producers={'producer'},expected_coherence='trusted-epoch')


@pytest.mark.parametrize('kwargs',[dict(trusted_producers={'other'},expected_coherence='trusted-epoch'),
    dict(trusted_producers={'producer'},expected_coherence='other'),
    dict(trusted_producers={'producer'},expected_coherence='trusted-epoch',max_bytes=10)])
def test_untrusted_incoherent_or_oversize_is_blocked(tmp_path,kwargs):
    data=snapshot_bytes(fixture_snapshot()); path=tmp_path/'s.json'; path.write_bytes(data)
    with pytest.raises(ValueError): load_snapshot(path,sha256(data).hexdigest(),**kwargs)


def test_actual_strattester_schema_is_not_fabricated_into_verified_data(tmp_path):
    from strattester.marketdata.schema import SCHEMA_SQL
    path=tmp_path/'actual.sqlite'
    with sqlite3.connect(path) as db: db.executescript(SCHEMA_SQL)
    before=path.read_bytes()
    with pytest.raises(ValueError,match='BLOCKED.*schema'):
        tuple(read_sqlite_bars(path,origin_ns=120))
    assert path.read_bytes()==before


def test_readonly_snapshot_remains_stable_while_writer_commits(tmp_path):
    path=tmp_path/'normalized.sqlite'
    row=asdict(fixture_snapshot().bars[0]); row.update(row.pop('instrument'))
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE research_bars ('+','.join('"'+k+'"' for k in row)+')')
        db.execute('INSERT INTO research_bars VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
    reader=read_sqlite_bars(path,origin_ns=120)
    assert next(reader).close==100.
    with sqlite3.connect(path) as db:
        row.update(candle_open_ns=60,candle_close_ns=120,event_ns=119,ingest_ns=120,available_ns=120,close=101.)
        db.execute('INSERT INTO research_bars VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
    assert list(reader)==[]
    assert len(tuple(read_sqlite_bars(path,origin_ns=120)))==2
