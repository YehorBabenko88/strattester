from __future__ import annotations
from pathlib import Path
import json,sqlite3
from strattester.engine.jobs import Job,JobState
class SQLiteStateStore:
    def __init__(self,path,con): self.path=Path(path); self.con=con
    @classmethod
    def open(cls,path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(p)
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
    def close(self): self.con.close()
