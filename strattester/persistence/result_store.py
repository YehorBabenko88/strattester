from __future__ import annotations
from pathlib import Path
import json,sqlite3,time

class ResultStore:
    def __init__(self,path,con): self.path=Path(path); self.con=con
    @classmethod
    def open(cls,path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(p,timeout=30)
        con.execute('PRAGMA journal_mode=WAL'); con.execute('PRAGMA busy_timeout=30000'); con.execute('PRAGMA synchronous=FULL'); con.execute('PRAGMA wal_autocheckpoint=1000')
        con.execute('''CREATE TABLE IF NOT EXISTS research_results(
            run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,strategy_version TEXT NOT NULL,
            created_at REAL NOT NULL,metrics TEXT NOT NULL,
            PRIMARY KEY(run_id,symbol,strategy_id,strategy_version))''')
        cols={r[1] for r in con.execute('PRAGMA table_info(research_results)')}
        if 'job_id' not in cols: con.execute('ALTER TABLE research_results ADD COLUMN job_id TEXT')
        if 'lease_token' not in cols: con.execute('ALTER TABLE research_results ADD COLUMN lease_token INTEGER NOT NULL DEFAULT 0')
        con.execute('CREATE INDEX IF NOT EXISTS ix_results_latest ON research_results(symbol,strategy_id,created_at DESC)')
        con.execute('''CREATE TABLE IF NOT EXISTS staged_research_results(
            stage_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,symbol TEXT NOT NULL,strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,created_at REAL NOT NULL,metrics TEXT NOT NULL,job_id TEXT,lease_token INTEGER NOT NULL DEFAULT 0)''')
        con.commit(); return cls(p,con)
    def put(self,run_id,symbol,strategy_id,strategy_version,metrics,created_at=None):
        created_at=time.time() if created_at is None else float(created_at)
        with self.con:
            self.con.execute('''INSERT OR REPLACE INTO research_results
                (run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token)
                VALUES(?,?,?,?,?,?,NULL,0)''',
                (run_id,symbol,strategy_id,strategy_version,created_at,json.dumps(metrics,sort_keys=True)))
    def stage(self,stage_id,run_id,symbol,strategy_id,strategy_version,metrics,created_at=None,job_id=None,lease_token=0):
        created_at=time.time() if created_at is None else float(created_at)
        with self.con:
            self.con.execute('''INSERT OR REPLACE INTO staged_research_results
                (stage_id,run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                (stage_id,run_id,symbol,strategy_id,strategy_version,created_at,json.dumps(metrics,sort_keys=True),job_id,int(lease_token)))

    def promote(self,stage_id,lease_validator):
        """Publish a staged result only while its external job lease is valid."""
        with self.con:
            row=self.con.execute('SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token FROM staged_research_results WHERE stage_id=?',(stage_id,)).fetchone()
            if row is None: return False
            if not lease_validator():
                self.con.execute('DELETE FROM staged_research_results WHERE stage_id=?',(stage_id,))
                return False
            existing=self.con.execute('''SELECT lease_token FROM research_results
                WHERE run_id=? AND symbol=? AND strategy_id=? AND strategy_version=?''',row[:4]).fetchone()
            if existing is not None and int(existing[0] or 0)>int(row[7] or 0):
                self.con.execute('DELETE FROM staged_research_results WHERE stage_id=?',(stage_id,))
                return False
            self.con.execute('''INSERT OR REPLACE INTO research_results
                (run_id,symbol,strategy_id,strategy_version,created_at,metrics,job_id,lease_token)
                VALUES(?,?,?,?,?,?,?,?)''',row)
            self.con.execute('DELETE FROM staged_research_results WHERE stage_id=?',(stage_id,))
            return True

    def discard_stage(self,stage_id):
        with self.con:
            self.con.execute('DELETE FROM staged_research_results WHERE stage_id=?',(stage_id,))

    def integrity_check(self):
        row=self.con.execute('PRAGMA quick_check').fetchone()
        return bool(row and str(row[0]).lower()=='ok')
    def latest(self,symbol,strategy_id):
        row=self.con.execute('''SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics
            FROM research_results WHERE symbol=? AND strategy_id=? ORDER BY created_at DESC LIMIT 1''',
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
