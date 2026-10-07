from __future__ import annotations
from pathlib import Path
import json,sqlite3,time
from strattester.engine.jobs import Job,JobState

_ACTIVE=(JobState.LEASED,JobState.RUNNING)

class SQLiteStateStore:
    def __init__(self,path,con): self.path=Path(path); self.con=con
    @classmethod
    def open(cls,path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(p,timeout=30)
        c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA busy_timeout=30000'); c.execute('PRAGMA synchronous=FULL')
        c.execute('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL)'''); c.commit()
        return cls(p,c)
    @staticmethod
    def _encode(job):
        d=job.__dict__.copy(); d['state']=job.state.value
        return json.dumps(d,separators=(',',':'))
    def put_job(self,job):
        with self.con: self.con.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)',(job.id,self._encode(job)))
    def _decode(self,payload):
        d=json.loads(payload); d['state']=JobState(d['state'])
        d.setdefault('lease_token',0); d.setdefault('target_node',None)
        return Job(**d)
    def get_job(self,job_id):
        r=self.con.execute('SELECT payload FROM jobs WHERE id=?',(job_id,)).fetchone()
        return self._decode(r[0]) if r else None
    def list_jobs(self): return [self._decode(r[0]) for r in self.con.execute('SELECT payload FROM jobs')]

    def claim_ready_jobs(self,owner:str,limit:int=1,now:float|None=None,lease_seconds:float=300,job_ids=None,node_id=None):
        now=time.time() if now is None else now
        claimed=[]
        self.con.execute('BEGIN IMMEDIATE')
        try:
            rows=list(self.con.execute('SELECT id,payload FROM jobs ORDER BY rowid'))
            jobs=[self._decode(x[1]) for x in rows]
            normalized=[]
            for job in jobs:
                recovered=job.recover_stale(now)
                normalized.append(recovered)
                if recovered!=job:
                    self.con.execute('UPDATE jobs SET payload=? WHERE id=?',(self._encode(recovered),recovered.id))
            jobs=normalized
            active_keys={
                j.resource_key for j in jobs
                if j.resource_key and j.state in _ACTIVE
                and (j.lease_until is None or j.lease_until>=now)
            }
            allowed=None if job_ids is None else set(job_ids)
            for job in jobs:
                if len(claimed)>=limit: break
                if allowed is not None and job.id not in allowed: continue
                if job.target_node is not None and node_id is not None and job.target_node!=node_id: continue
                if job.target_node is not None and node_id is None: continue
                if job.state not in (JobState.READY,JobState.RETRYABLE): continue
                if job.resource_key and job.resource_key in active_keys: continue
                leased=job.with_state(JobState.LEASED,lease_owner=owner,lease_until=now+lease_seconds,
                                      lease_token=job.lease_token+1,error=None)
                self.con.execute('UPDATE jobs SET payload=? WHERE id=?',(self._encode(leased),job.id))
                claimed.append(leased)
                if leased.resource_key: active_keys.add(leased.resource_key)
            self.con.commit()
            return claimed
        except Exception:
            self.con.rollback(); raise

    def renew_lease(self,job_id,owner,lease_token,lease_seconds=300,now=None):
        now=time.time() if now is None else now
        self.con.execute('BEGIN IMMEDIATE')
        try:
            row=self.con.execute('SELECT payload FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row is None:
                self.con.rollback(); return False
            job=self._decode(row[0])
            if job.lease_owner!=owner or job.lease_token!=lease_token or job.state not in _ACTIVE:
                self.con.rollback(); return False
            renewed=job.with_state(job.state,lease_until=now+lease_seconds)
            self.con.execute('UPDATE jobs SET payload=? WHERE id=?',(self._encode(renewed),job_id))
            self.con.commit(); return True
        except Exception:
            self.con.rollback(); raise

    def compare_and_swap_job(self,expected,replacement):
        self.con.execute('BEGIN IMMEDIATE')
        try:
            row=self.con.execute('SELECT payload FROM jobs WHERE id=?',(expected.id,)).fetchone()
            if row is None:
                self.con.rollback(); return False
            current=self._decode(row[0])
            if current.state!=expected.state or current.lease_token!=expected.lease_token or current.target_node!=expected.target_node or current.lease_owner!=expected.lease_owner:
                self.con.rollback(); return False
            self.con.execute('UPDATE jobs SET payload=? WHERE id=?',(self._encode(replacement),expected.id))
            self.con.commit(); return True
        except Exception:
            self.con.rollback(); raise

    def lease_valid(self,job_id,owner,lease_token,now=None):
        now=time.time() if now is None else float(now)
        job=self.get_job(job_id)
        return bool(job and job.lease_owner==owner and job.lease_token==lease_token
                    and job.state in _ACTIVE and (job.lease_until is None or job.lease_until>=now))

    def transition_claimed(self,job_id,owner,lease_token,state,**changes):
        self.con.execute('BEGIN IMMEDIATE')
        try:
            row=self.con.execute('SELECT payload FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row is None:
                self.con.rollback(); return False
            job=self._decode(row[0])
            if job.lease_owner!=owner or job.lease_token!=lease_token:
                self.con.rollback(); return False
            updated=job.with_state(state,**changes)
            self.con.execute('UPDATE jobs SET payload=? WHERE id=?',(self._encode(updated),job_id))
            self.con.commit(); return True
        except Exception:
            self.con.rollback(); raise

    def close(self): self.con.close()
