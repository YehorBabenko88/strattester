"""Dedicated SQLite coordinator state; never infer exchange history from observations."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3

STATES=('DISCOVERED','SYNCING','PARTIAL','READY','RUNNING','COMPLETED','FAILED','BLOCKED')

def canonical(value,limit=1024*1024):
    pieces=[];size=0
    for piece in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(value):
        size+=len(piece.encode('utf-8'))
        if size>limit:raise ValueError('serialized resource budget')
        pieces.append(piece)
    return ''.join(pieces)

def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

class DataFirstStateStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS df_instruments(category TEXT,symbol TEXT,metadata TEXT NOT NULL,
             observed_at INTEGER NOT NULL,history TEXT,PRIMARY KEY(category,symbol));
            CREATE TABLE IF NOT EXISTS df_snapshots(category TEXT PRIMARY KEY,observed_at INTEGER,digest TEXT);
            CREATE TABLE IF NOT EXISTS df_instrument_observations(category TEXT,symbol TEXT,observed_at INTEGER,
             metadata TEXT NOT NULL,source_digest TEXT NOT NULL,kind TEXT NOT NULL,
             PRIMARY KEY(category,symbol,observed_at,kind));
            CREATE TABLE IF NOT EXISTS df_jobs(id TEXT PRIMARY KEY,partition_key TEXT NOT NULL,payload TEXT NOT NULL,
             state TEXT NOT NULL,progress TEXT NOT NULL DEFAULT '{}',reason TEXT NOT NULL DEFAULT '',
             owner TEXT,lease_until INTEGER,token INTEGER NOT NULL DEFAULT 0,result TEXT);
            CREATE TABLE IF NOT EXISTS df_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT,state TEXT,
             reason TEXT,observed_at INTEGER);
            ''')

    @contextmanager
    def connection(self):
        c=sqlite3.connect(self.path,timeout=5)
        c.row_factory=sqlite3.Row
        try:
            c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL');c.execute('PRAGMA busy_timeout=5000')
            yield c
            c.commit()
        except BaseException:c.rollback();raise
        finally:c.close()

    @staticmethod
    def metadata(category,row):
        if category not in ('linear','inverse','spot') or type(row) is not dict:
            raise ValueError('instrument market identity')
        symbol=row.get('symbol')
        if type(symbol) is not str or re.fullmatch('[A-Z0-9_.-]{1,80}',symbol) is None:
            raise ValueError('instrument symbol identity')
        fields=('symbol','status','launchTime','deliveryTime','fundingInterval','contractType','marketRegion','symbolId','baseCoin','quoteCoin')
        result={key:row.get(key) for key in fields};result['category']=category
        if result['status'] not in ('Trading','PendingOpen','PreLaunch','Delivering','Closed','Settled','Suspended','MISSING'):
            raise ValueError('unknown instrument status')
        if any(value is not None and (type(value) not in (str,int) or len(str(value))>128) for value in result.values()):
            raise ValueError('instrument metadata budget/types')
        canonical(result,2048)
        return result

    def snapshot(self,category,rows,observed_at):
        if category not in ('linear','inverse','spot') or type(observed_at) is not int or not 0<=observed_at<2**63:raise ValueError('snapshot identity/time')
        items=[self.metadata(category,row) for row in rows]
        if len({r['symbol'] for r in items})!=len(items):raise ValueError('duplicate instrument snapshot')
        h=hashlib.sha256()
        for item in sorted(items,key=lambda x:x['symbol']):h.update(canonical(item).encode());h.update(b'\n')
        snapshot_hash=h.hexdigest()
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM df_snapshots WHERE category=?',(category,)).fetchone()
            if old and (observed_at<old['observed_at'] or observed_at==old['observed_at'] and snapshot_hash!=old['digest']):
                raise ValueError('nonmonotonic or conflicting discovery')
            if old and observed_at==old['observed_at']:return
            symbols={r['symbol'] for r in items}
            for row in c.execute('SELECT symbol,metadata FROM df_instruments WHERE category=?',(category,)).fetchall():
                metadata=json.loads(row['metadata'])
                if row['symbol'] not in symbols and metadata['status'] in ('Trading','PendingOpen','PreLaunch','MISSING'):
                    metadata['status']='MISSING'
                    c.execute('UPDATE df_instruments SET metadata=? WHERE category=? AND symbol=?',
                              (canonical(metadata),category,row['symbol']))
                    c.execute('INSERT OR IGNORE INTO df_instrument_observations VALUES(?,?,?,?,?,?)',
                              (category,row['symbol'],observed_at,canonical(metadata),snapshot_hash,'OBSERVED_MISSING_NOT_DELIST'))
            for item in items:
                c.execute('INSERT INTO df_instruments(category,symbol,metadata,observed_at) VALUES(?,?,?,?) ON CONFLICT(category,symbol) DO UPDATE SET metadata=excluded.metadata,observed_at=excluded.observed_at',
                          (category,item['symbol'],canonical(item),observed_at))
                c.execute('INSERT OR IGNORE INTO df_instrument_observations VALUES(?,?,?,?,?,?)',
                          (category,item['symbol'],observed_at,canonical(item),snapshot_hash,'CURRENT_EXCHANGE_OBSERVATION'))
            c.execute('INSERT OR REPLACE INTO df_snapshots VALUES(?,?,?)',(category,observed_at,snapshot_hash))

    def register_history(self,category,row,intervals,*,source_sha256,observed_at):
        """Explicit caller-supplied archive facts, not producer authentication."""
        item=self.metadata(category,row)
        if type(source_sha256) is not str or re.fullmatch('[0-9a-f]{64}',source_sha256) is None:raise ValueError('history provenance')
        previous=-1
        for start,end in intervals:
            if type(start) is not int or type(end) is not int or not 0<=start<end<2**63 or previous>start:raise ValueError('activity intervals')
            previous=end
        if not intervals:raise ValueError('empty historical activity')
        history=canonical({'intervals':intervals,'source_sha256':source_sha256})
        with self.connection() as c:
            c.execute('INSERT INTO df_instruments VALUES(?,?,?,?,?) ON CONFLICT(category,symbol) DO UPDATE SET metadata=excluded.metadata,observed_at=excluded.observed_at,history=excluded.history',
                      (category,item['symbol'],canonical(item),observed_at,history))
            c.execute('INSERT OR IGNORE INTO df_instrument_observations VALUES(?,?,?,?,?,?)',
                      (category,item['symbol'],observed_at,canonical(item),source_sha256,'CALLER_PROVIDED_ARCHIVE_NOT_ATTESTATION'))

    def instruments(self,categories=None):
        with self.connection() as c:
            rows=c.execute('SELECT * FROM df_instruments ORDER BY category,symbol').fetchall()
        return [dict(metadata=json.loads(r['metadata']),history=json.loads(r['history']) if r['history'] else None,
                     observed_at=r['observed_at']) for r in rows if categories is None or r['category'] in categories]

    def plan(self,payload,now):
        text=canonical(payload);key=hashlib.sha256(text.encode()).hexdigest()
        partition=canonical([payload['instrument']['category'],payload['instrument']['symbol']])
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            changed=c.execute('INSERT OR IGNORE INTO df_jobs(id,partition_key,payload,state) VALUES(?,?,?,?)',
                              (key,partition,text,'DISCOVERED')).rowcount
            if changed:c.execute('INSERT INTO df_events(job_id,state,reason,observed_at) VALUES(?,?,?,?)',(key,'DISCOVERED','',now))
        return key

    def jobs(self):
        with self.connection() as c:rows=c.execute('SELECT j.*,COALESCE((SELECT MAX(seq) FROM df_events e WHERE e.job_id=j.id),0) AS last_event FROM df_jobs j ORDER BY id').fetchall()
        return [self.decode(r) for r in rows]

    def get(self,key):
        with self.connection() as c:row=c.execute('SELECT * FROM df_jobs WHERE id=?',(key,)).fetchone()
        return self.decode(row) if row else None

    @staticmethod
    def decode(row):
        out=dict(row)
        for key in ('payload','progress','result'):
            out[key]=json.loads(out[key]) if out[key] is not None else None
        return out

    def claim(self,key,owner,now,lease_ms,max_active=None):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM df_jobs WHERE id=?',(key,)).fetchone()
            if not row or row['state'] in ('COMPLETED','FAILED','BLOCKED'):return None
            if row['lease_until'] is not None and row['lease_until']>now:return None
            if row['state']=='RUNNING':
                c.execute("UPDATE df_jobs SET state='BLOCKED',reason='UNCERTAIN_EXECUTION_AFTER_LEASE',owner=NULL,lease_until=NULL WHERE id=?",(key,))
                c.execute('INSERT INTO df_events(job_id,state,reason,observed_at) VALUES(?,?,?,?)',(key,'BLOCKED','UNCERTAIN_EXECUTION_AFTER_LEASE',now))
                return None
            if max_active is not None and c.execute('SELECT COUNT(*) FROM df_jobs WHERE lease_until>?',(now,)).fetchone()[0]>=max_active:
                return None
            busy=c.execute('SELECT 1 FROM df_jobs WHERE partition_key=? AND id<>? AND lease_until>? LIMIT 1',(row['partition_key'],key,now)).fetchone()
            if busy:return None
            token=row['token']+1
            c.execute('UPDATE df_jobs SET owner=?,lease_until=?,token=? WHERE id=?',(owner,now+lease_ms,token,key))
            return token

    def transition(self,key,owner,token,now,state,*,reason='',progress=None,result=None,release=False):
        if state not in STATES:raise ValueError('scheduler state')
        result_text=canonical(result) if result is not None else None
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM df_jobs WHERE id=?',(key,)).fetchone()
            if not row or row['owner']!=owner or row['token']!=token or row['lease_until']<now:
                raise RuntimeError('scheduler lease fenced')
            if state in ('RUNNING','COMPLETED'):
                payload=json.loads(row['payload']);instrument=payload['instrument']
                actual=c.execute('SELECT metadata,history FROM df_instruments WHERE category=? AND symbol=?',
                                 (instrument['category'],instrument['symbol'])).fetchone()
                if actual is None or json.loads(actual['metadata'])!=instrument:
                    raise ValueError('instrument publication fence')
                history=json.loads(actual['history']) if actual['history'] else None
                if (digest(history) if history else None)!=payload.get('history_fingerprint'):
                    raise ValueError('archive history publication fence')
            if state=='COMPLETED' and (result is None or row['state']!='RUNNING'):raise ValueError('completion admission')
            c.execute('UPDATE df_jobs SET state=?,reason=?,progress=?,result=COALESCE(?,result),owner=?,lease_until=? WHERE id=?',
                      (state,reason,canonical(progress if progress is not None else json.loads(row['progress'])),result_text,
                       None if release else owner,None if release else row['lease_until'],key))
            c.execute('INSERT INTO df_events(job_id,state,reason,observed_at) VALUES(?,?,?,?)',(key,state,reason,now))

    def renew(self,key,owner,token,now,lease_ms):
        with self.connection() as c:
            changed=c.execute('UPDATE df_jobs SET lease_until=? WHERE id=? AND owner=? AND token=? AND lease_until>=?',
                              (now+lease_ms,key,owner,token,now)).rowcount
            if not changed:raise RuntimeError('scheduler lease fenced')

    def events(self,key):
        with self.connection() as c:return [dict(r) for r in c.execute('SELECT * FROM df_events WHERE job_id=? ORDER BY seq',(key,))]
