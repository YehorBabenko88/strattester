from __future__ import annotations
from pathlib import Path
import json,sqlite3,time
from strattester.engine.jobs import Job,JobState
class SQLiteStateStore:
    def __init__(self,path,con): self.path=Path(path); self.con=con
    @classmethod
    def open(cls,path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(p,timeout=30)
        c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA busy_timeout=30000')
        c.execute('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL)'''); c.commit()
        return cls(p,c)
    def put_job(self,job):
        d=job.__dict__.copy(); d['state']=job.state.value
        with self.con: self.con.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)',(job.id,json.dumps(d)))
    def _decode(self,payload):
        d=json.loads(payload); d['state']=JobState(d['state']); return Job(**d)
    def get_job(self,job_id):
        r=self.con.execute('SELECT payload FROM jobs WHERE id=?',(job_id,)).fetchone()
        return self._decode(r[0]) if r else None
    def list_jobs(self): return [self._decode(r[0]) for r in self.con.execute('SELECT payload FROM jobs')]
    def claim_ready_jobs(self,owner:str,limit:int=1,now:float|None=None,lease_seconds:float=300):
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
                    d=recovered.__dict__.copy(); d['state']=recovered.state.value
                    self.con.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(d),recovered.id))
            jobs=normalized
            active_keys={
                j.resource_key for j in jobs
                if j.resource_key and j.state in (JobState.LEASED,JobState.RUNNING)
                and (j.lease_until is None or j.lease_until>=now)
            }
            for job in jobs:
                if len(claimed)>=limit: break
                if job.state not in (JobState.READY,JobState.RETRYABLE): continue
                if job.resource_key and job.resource_key in active_keys: continue
                leased=job.with_state(JobState.LEASED,lease_owner=owner,lease_until=now+lease_seconds,error=None)
                d=leased.__dict__.copy(); d['state']=leased.state.value
                self.con.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(d),job.id))
                claimed.append(leased)
                if leased.resource_key: active_keys.add(leased.resource_key)
            self.con.commit()
            return claimed
        except Exception:
            self.con.rollback(); raise

    def close(self): self.con.close()
