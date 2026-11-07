from __future__ import annotations
from pathlib import Path
import json,sqlite3,time,uuid
from contextlib import contextmanager
import hashlib,re

class ResultStore:
    def __init__(self,path,con): self.path=Path(path); self.con=con; self.producer_epoch=str(uuid.uuid4())
    @classmethod
    def open(cls,path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(p,timeout=30)
        con.execute('PRAGMA journal_mode=WAL'); con.execute('PRAGMA busy_timeout=30000'); con.execute('PRAGMA synchronous=FULL'); con.execute('PRAGMA wal_autocheckpoint=1000')
        # Serialize first-upgrade introspection and DDL across independent openers.
        con.execute('BEGIN IMMEDIATE')
        con.execute('''CREATE TABLE IF NOT EXISTS research_results(
            run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,strategy_version TEXT NOT NULL,
            created_at REAL NOT NULL,metrics TEXT NOT NULL,
            PRIMARY KEY(run_id,symbol,strategy_id,strategy_version))''')
        cols={r[1] for r in con.execute('PRAGMA table_info(research_results)')}
        if 'job_id' not in cols: con.execute('ALTER TABLE research_results ADD COLUMN job_id TEXT')
        if 'lease_token' not in cols: con.execute('ALTER TABLE research_results ADD COLUMN lease_token INTEGER NOT NULL DEFAULT 0')
        if 'node_generation' not in cols: con.execute('ALTER TABLE research_results ADD COLUMN node_generation INTEGER NOT NULL DEFAULT 0')
        con.execute('CREATE INDEX IF NOT EXISTS ix_results_latest ON research_results(symbol,strategy_id,created_at DESC)')
        con.execute('''CREATE TABLE IF NOT EXISTS staged_research_results(
            stage_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,created_at REAL NOT NULL,metrics TEXT NOT NULL,job_id TEXT,lease_token INTEGER NOT NULL DEFAULT 0,node_generation INTEGER NOT NULL DEFAULT 0)''')
        staged_cols={r[1] for r in con.execute('PRAGMA table_info(staged_research_results)')}
        if 'job_id' not in staged_cols:con.execute('ALTER TABLE staged_research_results ADD COLUMN job_id TEXT')
        if 'lease_token' not in staged_cols:con.execute('ALTER TABLE staged_research_results ADD COLUMN lease_token INTEGER NOT NULL DEFAULT 0')
        if 'node_generation' not in staged_cols:con.execute('ALTER TABLE staged_research_results ADD COLUMN node_generation INTEGER NOT NULL DEFAULT 0')
        for table in ('research_results','staged_research_results'):
            existing={r[1] for r in con.execute('PRAGMA table_info('+table+')')}
            columns={'result_kind':"TEXT NOT NULL DEFAULT 'FINANCIAL'",'artifact_descriptor':'BLOB',
                     'artifact_descriptor_sha256':'TEXT','artifact_sha256':'TEXT',
                     'original_intent_sha256':'TEXT','publication_receipt':'BLOB'}
            for column,kind in columns.items():
                if column not in existing:con.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' '+kind)
        con.execute("CREATE TABLE IF NOT EXISTS owned_runs(run_id TEXT PRIMARY KEY,state TEXT NOT NULL,record TEXT)")
        con.execute("CREATE TRIGGER IF NOT EXISTS owned_complete_no_replace BEFORE INSERT ON owned_runs WHEN EXISTS(SELECT 1 FROM owned_runs WHERE run_id=NEW.run_id AND state='COMPLETE') BEGIN SELECT RAISE(ABORT,'immutable completed run'); END")
        con.execute("CREATE TRIGGER IF NOT EXISTS owned_complete_immutable BEFORE UPDATE ON owned_runs WHEN OLD.state='COMPLETE' BEGIN SELECT RAISE(ABORT,'immutable completed run'); END")
        con.execute("CREATE TRIGGER IF NOT EXISTS owned_complete_no_delete BEFORE DELETE ON owned_runs WHEN OLD.state='COMPLETE' BEGIN SELECT RAISE(ABORT,'immutable completed run'); END")
        con.commit(); return cls(p,con)
    def put(self,run_id,symbol,strategy_id,strategy_version,metrics,created_at=None):
        created_at=time.time() if created_at is None else float(created_at)
        with self._serialized_write():
            self._reject_artifact_collision(None,(run_id,symbol,strategy_id,strategy_version))
            self.con.execute('''INSERT OR REPLACE INTO research_results
                (run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token,node_generation)
                VALUES(?,?,?,?,?,?,NULL,0,0)''',
                (run_id,symbol,strategy_id,strategy_version,created_at,json.dumps(metrics,sort_keys=True)))
    def stage(self,stage_id,run_id,symbol,strategy_id,strategy_version,metrics,created_at=None,job_id=None,lease_token=0,node_generation=0):
        created_at=time.time() if created_at is None else float(created_at)
        with self._serialized_write():
            self._reject_artifact_collision(stage_id,(run_id,symbol,strategy_id,strategy_version))
            self.con.execute('''INSERT OR REPLACE INTO staged_research_results
                (stage_id,run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token,node_generation)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (stage_id,run_id,symbol,strategy_id,strategy_version,created_at,json.dumps(metrics,sort_keys=True),job_id,int(lease_token),int(node_generation)))

    def promote(self,stage_id,lease_validator):
        """Publish a staged result only while its external job lease is valid."""
        with self._serialized_write():
            row=self.con.execute("SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token,node_generation FROM staged_research_results WHERE stage_id=? AND result_kind='FINANCIAL'",(stage_id,)).fetchone()
            if row is None: return False
            self._reject_artifact_collision(stage_id,row[:4])
            if not lease_validator():
                self.con.execute('DELETE FROM staged_research_results WHERE stage_id=?',(stage_id,))
                return False
            existing=self.con.execute('''SELECT lease_token FROM research_results
                WHERE run_id=? AND symbol=? AND strategy_id=? AND strategy_version=?''',row[:4]).fetchone()
            if existing is not None and int(existing[0] or 0)>int(row[7] or 0):
                self.con.execute('DELETE FROM staged_research_results WHERE stage_id=?',(stage_id,))
                return False
            self.con.execute('''INSERT OR REPLACE INTO research_results
                (run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token,node_generation)
                VALUES(?,?,?,?,?,?,?,?,?)''',row)
            self.con.execute('DELETE FROM staged_research_results WHERE stage_id=?',(stage_id,))
            return True

    def recover_staged(self,lease_validator):
        """Revalidate every crash-left stage; never publish merely because it survived reboot."""
        rows=self.con.execute("SELECT stage_id,job_id,lease_token,node_generation FROM staged_research_results WHERE result_kind='FINANCIAL' ORDER BY stage_id").fetchall()
        promoted=discarded=0
        for stage_id,job_id,lease_token,node_generation in rows:
            valid=lambda j=job_id,t=lease_token,g=node_generation: bool(lease_validator(j,int(t or 0),int(g or 0)))
            if self.promote(stage_id,valid):promoted+=1
            else:discarded+=1
        return {'promoted':promoted,'discarded':discarded}

    def cleanup_staged(self,older_than,limit=1000):
        older_than=float(older_than);limit=int(limit)
        if limit<1:raise ValueError('cleanup limit must be positive')
        with self._serialized_write():
            ids=[r[0] for r in self.con.execute(
                "SELECT stage_id FROM staged_research_results WHERE result_kind='FINANCIAL' AND created_at<? ORDER BY created_at LIMIT ?",
                (older_than,limit)).fetchall()]
            if ids:self.con.executemany("DELETE FROM staged_research_results WHERE stage_id=? AND result_kind='FINANCIAL'",((x,) for x in ids))
        return len(ids)

    def discard_stage(self,stage_id):
        with self.con:
            self.con.execute("DELETE FROM staged_research_results WHERE stage_id=? AND result_kind='FINANCIAL'",(stage_id,))

    def integrity_check(self):
        row=self.con.execute('PRAGMA quick_check').fetchone()
        return bool(row and str(row[0]).lower()=='ok')
    def latest_fenced(self,symbol,strategy_id,authority_validator):
        rows=self.con.execute('''SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token,node_generation
            FROM research_results WHERE result_kind='FINANCIAL' AND symbol=? AND strategy_id=? ORDER BY created_at DESC''',
            (symbol,strategy_id)).fetchall()
        for row in rows:
            # Legacy/unfenced rows are never silently trusted by distributed consumers.
            if row[6] is None:continue
            if authority_validator(row[6],int(row[7] or 0),int(row[8] or 0)):
                return {'run_id':row[0],'symbol':row[1],'strategy_id':row[2],'strategy_version':row[3],
                        'created_at':row[4],'metrics':json.loads(row[5]),'job_id':row[6],
                        'lease_token':int(row[7] or 0),'node_generation':int(row[8] or 0)}
        return None

    def begin_owned(self,run_id):
        with self.con:
            self.con.execute("INSERT INTO owned_runs VALUES(?,'RUNNING',NULL)",(run_id,))

    def abort_owned(self,run_id):
        with self.con:
            self.con.execute("UPDATE owned_runs SET state='ABORTED' WHERE run_id=? AND state='RUNNING'",(run_id,))

    def complete_owned(self,run_id,record,lease_validator):
        from strattester.research.provenance import canonical,validate
        if record.get('run_id')!=run_id or validate(record): raise ValueError('RECORD_INVALID')
        with self.con:
            if not lease_validator(): raise RuntimeError('PUBLICATION_FENCED')
            cursor=self.con.execute("UPDATE owned_runs SET state='COMPLETE',record=? WHERE run_id=? AND state='RUNNING'",(canonical(record).decode(),run_id))
            if cursor.rowcount!=1: raise RuntimeError('RUN_STATE_INVALID')
    def latest(self,symbol,strategy_id):
        row=self.con.execute('''SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics
            FROM research_results WHERE result_kind='FINANCIAL' AND symbol=? AND strategy_id=? ORDER BY created_at DESC LIMIT 1''',
            (symbol,strategy_id)).fetchone()
        if row is None:return None
        return {'run_id':row[0],'symbol':row[1],'strategy_id':row[2],'strategy_version':row[3],
                'created_at':row[4],'metrics':json.loads(row[5])}
    def checkpoint_wal(self,mode='PASSIVE'):
        mode=str(mode).upper()
        if mode not in ('PASSIVE','FULL','RESTART','TRUNCATE'):
            raise ValueError('unsupported WAL checkpoint mode')
        return self.con.execute(f'PRAGMA wal_checkpoint({mode})').fetchone()
    def close(self):
        try: self.checkpoint_wal('PASSIVE')
        finally: self.con.close()

    @contextmanager
    def _serialized_write(self):
        """Acquire SQLite's writer reservation before cross-table identity reads."""
        with self.con:
            if self.con.in_transaction:
                # Upgrade an existing caller transaction before reading identities.
                # SQLITE_BUSY on a stale snapshot fails closed; never precheck unlocked.
                self.con.execute('UPDATE research_results SET created_at=created_at WHERE 0')
            else:self.con.execute('BEGIN IMMEDIATE')
            yield

    def _reject_artifact_collision(self,stage_id,key):
        for table in ('research_results','staged_research_results'):
            query="SELECT 1 FROM "+table+" WHERE result_kind='ARTIFACT' AND ((run_id,symbol,strategy_id,strategy_version)=(?,?,?,?)"
            args=tuple(key)
            if table=='staged_research_results' and stage_id is not None:
                query+=' OR stage_id=?';args+=(stage_id,)
            if self.con.execute(query+') LIMIT 1',args).fetchone():raise ValueError('ARTIFACT_STAGE_CONFLICT')

    def stage_gateway_artifact(self,stage_id,run_id,symbol,operation_id,operation_revision,raw_descriptor,*,artifact_sha256,original_intent_sha256):
        """LOCAL opaque byte staging; no semantic/source/publication admission."""
        # Exact byte preflight precedes hashing; no caller-defined bytes protocols.
        if type(raw_descriptor) is not bytes or not 0<len(raw_descriptor)<=65536:raise ValueError('ARTIFACT_STAGE_INVALID')
        for value in (stage_id,run_id,symbol,operation_id):
            if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}',value) is None:raise ValueError('ARTIFACT_STAGE_INVALID')
        if type(operation_revision) is not str or re.fullmatch(r'0|[1-9][0-9]{0,18}',operation_revision) is None or int(operation_revision)>2**63-1:raise ValueError('ARTIFACT_STAGE_INVALID')
        for value in (artifact_sha256,original_intent_sha256):
            if type(value) is not str or re.fullmatch(r'[0-9a-f]{64}',value) is None:raise ValueError('ARTIFACT_STAGE_INVALID')
        descriptor_sha=hashlib.sha256(raw_descriptor).hexdigest()
        key=(run_id,symbol,operation_id,operation_revision)
        expected=key+(raw_descriptor,descriptor_sha,artifact_sha256,original_intent_sha256)
        fields='run_id,symbol,strategy_id,strategy_version,artifact_descriptor,artifact_descriptor_sha256,artifact_sha256,original_intent_sha256,result_kind'
        with self._serialized_write():
            found=False
            for table in ('research_results','staged_research_results'):
                query='SELECT '+fields+' FROM '+table+' WHERE (run_id,symbol,strategy_id,strategy_version)=(?,?,?,?)';args=key
                if table=='staged_research_results':query+=' OR stage_id=?';args+=(stage_id,)
                for row in self.con.execute(query,args):
                    if row[-1]!='ARTIFACT' or row[:-1]!=expected:raise ValueError('ARTIFACT_STAGE_CONFLICT')
                    found=True
            if found:return None
            self.con.execute('''INSERT INTO staged_research_results
                (stage_id,run_id,symbol,strategy_id,strategy_version,created_at,metrics,
                 result_kind,artifact_descriptor,artifact_descriptor_sha256,artifact_sha256,original_intent_sha256)
                VALUES(?,?,?,?,?,?,?,'ARTIFACT',?,?,?,?)''',
                (stage_id,*key,time.time(),'{}',raw_descriptor,descriptor_sha,artifact_sha256,original_intent_sha256))
        return None

    def project_gateway_artifact_commit(self,stage_id,*,actual_receipt_handle,expected_authority):
        # Actual issuer/type/native protocol is not frozen. Never inspect foreign
        # objects or accept a dict/callback as authority. UNKNOWN stages survive.
        raise RuntimeError('ARTIFACT_AUTHORITY_ABI_UNAVAILABLE')

    def read_gateway_artifact(self,run_id,symbol,operation_id,operation_revision):
        raise RuntimeError('ARTIFACT_AUTHORITY_ABI_UNAVAILABLE')
