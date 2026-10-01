from __future__ import annotations
import json
from strattester.engine.jobs import Job,JobState
class PostgresStateStore:
    def __init__(self,connection): self.con=connection
    @classmethod
    def connect(cls,dsn):
        try: import psycopg
        except ImportError as exc: raise RuntimeError('PostgreSQL support requires psycopg') from exc
        con=psycopg.connect(dsn)
        with con.cursor() as cur: cur.execute('CREATE TABLE IF NOT EXISTS strattester_jobs(id TEXT PRIMARY KEY,payload JSONB NOT NULL)')
        con.commit(); return cls(con)
    def put_job(self,job):
        d=job.__dict__.copy(); d['state']=job.state.value
        with self.con.cursor() as cur: cur.execute('INSERT INTO strattester_jobs(id,payload) VALUES(%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(job.id,json.dumps(d)))
        self.con.commit()
    @staticmethod
    def _decode(d):
        if isinstance(d,str): d=json.loads(d)
        d=dict(d); d['state']=JobState(d['state']); return Job(**d)
    def get_job(self,job_id):
        with self.con.cursor() as cur: cur.execute('SELECT payload FROM strattester_jobs WHERE id=%s',(job_id,)); r=cur.fetchone()
        return self._decode(r[0]) if r else None
    def list_jobs(self):
        with self.con.cursor() as cur: cur.execute('SELECT payload FROM strattester_jobs'); rows=cur.fetchall()
        return [self._decode(r[0]) for r in rows]
    def close(self): self.con.close()
