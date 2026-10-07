from __future__ import annotations
import json,time
from strattester.engine.jobs import Job,JobState

_ACTIVE=(JobState.LEASED,JobState.RUNNING)

class PostgresStateStore:
    def __init__(self,connection,dsn=None): self.con=connection; self.dsn=dsn
    def reconnect(self):
        if not self.dsn:
            return False
        try:
            import psycopg
            try: self.con.close()
            except Exception: pass
            self.con=psycopg.connect(self.dsn)
            return True
        except Exception:
            return False
    @classmethod
    def connect(cls,dsn):
        try: import psycopg
        except ImportError as exc: raise RuntimeError('PostgreSQL support requires psycopg') from exc
        con=psycopg.connect(dsn)
        with con.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS strattester_jobs(id TEXT PRIMARY KEY,payload JSONB NOT NULL)')
            cur.execute('CREATE TABLE IF NOT EXISTS strattester_nodes(node_id TEXT PRIMARY KEY,last_seen DOUBLE PRECISION NOT NULL,meta JSONB NOT NULL DEFAULT \'{}\'::jsonb)')
        con.commit(); return cls(con,dsn)
    @staticmethod
    def _encode(job):
        d=job.__dict__.copy(); d['state']=job.state.value
        return d
    def put_job(self,job):
        with self.con.cursor() as cur:
            cur.execute('INSERT INTO strattester_jobs(id,payload) VALUES(%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                        (job.id,json.dumps(self._encode(job))))
        self.con.commit()
    @staticmethod
    def _decode(d):
        if isinstance(d,str): d=json.loads(d)
        d=dict(d); d['state']=JobState(d['state'])
        d.setdefault('lease_token',0); d.setdefault('target_node',None)
        return Job(**d)
    def get_job(self,job_id):
        with self.con.cursor() as cur:
            cur.execute('SELECT payload FROM strattester_jobs WHERE id=%s',(job_id,)); r=cur.fetchone()
        return self._decode(r[0]) if r else None
    def list_jobs(self):
        with self.con.cursor() as cur: cur.execute('SELECT payload FROM strattester_jobs ORDER BY id'); rows=cur.fetchall()
        return [self._decode(r[0]) for r in rows]

    def claim_ready_jobs(self,owner:str,limit:int=1,now:float|None=None,lease_seconds:float=300,job_ids=None,node_id=None):
        now=time.time() if now is None else float(now)
        allowed=None if job_ids is None else set(job_ids)
        claimed=[]
        try:
            with self.con.cursor() as cur:
                cur.execute('SELECT id,payload FROM strattester_jobs FOR UPDATE SKIP LOCKED')
                rows=cur.fetchall()
                jobs=[]
                for job_id,payload in rows:
                    job=self._decode(payload)
                    recovered=job.recover_stale(now)
                    if recovered!=job:
                        cur.execute('UPDATE strattester_jobs SET payload=%s::jsonb WHERE id=%s',
                                    (json.dumps(self._encode(recovered)),job_id))
                    jobs.append(recovered)
                active_keys={
                    j.resource_key for j in jobs
                    if j.resource_key and j.state in _ACTIVE and (j.lease_until is None or j.lease_until>=now)
                }
                for job in jobs:
                    if len(claimed)>=limit: break
                    if allowed is not None and job.id not in allowed: continue
                    if job.target_node is not None and node_id is not None and job.target_node!=node_id: continue
                    if job.target_node is not None and node_id is None: continue
                    if job.state not in (JobState.READY,JobState.RETRYABLE): continue
                    if job.resource_key and job.resource_key in active_keys: continue
                    if job.resource_key:
                        cur.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0))",(job.resource_key,))
                        if not bool(cur.fetchone()[0]): continue
                        cur.execute("""SELECT payload FROM strattester_jobs
                            WHERE payload->>'resource_key'=%s
                              AND payload->>'state' IN ('LEASED','RUNNING')
                              AND COALESCE((payload->>'lease_until')::double precision,0)>=%s
                              AND id<>%s LIMIT 1""",(job.resource_key,now,job.id))
                        if cur.fetchone() is not None: continue
                    leased=job.with_state(JobState.LEASED,lease_owner=owner,lease_until=now+lease_seconds,
                                          lease_token=job.lease_token+1,error=None)
                    cur.execute('UPDATE strattester_jobs SET payload=%s::jsonb WHERE id=%s',
                                (json.dumps(self._encode(leased)),job.id))
                    claimed.append(leased)
                    if leased.resource_key: active_keys.add(leased.resource_key)
            self.con.commit(); return claimed
        except Exception:
            self.con.rollback(); raise

    def renew_lease(self,job_id,owner,lease_token,lease_seconds=300,now=None):
        now=time.time() if now is None else float(now)
        try:
            with self.con.cursor() as cur:
                cur.execute('SELECT payload FROM strattester_jobs WHERE id=%s FOR UPDATE',(job_id,))
                row=cur.fetchone()
                if row is None:
                    self.con.rollback(); return False
                job=self._decode(row[0])
                if job.lease_owner!=owner or job.lease_token!=lease_token or job.state not in _ACTIVE:
                    self.con.rollback(); return False
                renewed=job.with_state(job.state,lease_until=now+lease_seconds)
                cur.execute('UPDATE strattester_jobs SET payload=%s::jsonb WHERE id=%s',
                            (json.dumps(self._encode(renewed)),job_id))
            self.con.commit(); return True
        except Exception:
            self.con.rollback(); raise

    def transition_claimed(self,job_id,owner,lease_token,state,**changes):
        try:
            with self.con.cursor() as cur:
                cur.execute('SELECT payload FROM strattester_jobs WHERE id=%s FOR UPDATE',(job_id,))
                row=cur.fetchone()
                if row is None:
                    self.con.rollback(); return False
                job=self._decode(row[0])
                if job.lease_owner!=owner or job.lease_token!=lease_token:
                    self.con.rollback(); return False
                updated=job.with_state(state,**changes)
                cur.execute('UPDATE strattester_jobs SET payload=%s::jsonb WHERE id=%s',
                            (json.dumps(self._encode(updated)),job_id))
            self.con.commit(); return True
        except Exception:
            self.con.rollback(); raise

    def heartbeat_node(self,node_id,now=None,meta=None):
        now=time.time() if now is None else float(now)
        payload=json.dumps(meta or {})
        try:
            with self.con.cursor() as cur:
                cur.execute('''INSERT INTO strattester_nodes(node_id,last_seen,meta)
                    VALUES(%s,%s,%s::jsonb)
                    ON CONFLICT(node_id) DO UPDATE SET last_seen=excluded.last_seen,meta=excluded.meta''',
                    (str(node_id),now,payload))
            self.con.commit()
        except Exception:
            self.con.rollback(); raise

    def live_nodes(self,stale_after=30,now=None):
        now=time.time() if now is None else float(now)
        cutoff=now-float(stale_after)
        with self.con.cursor() as cur:
            cur.execute('SELECT node_id FROM strattester_nodes WHERE last_seen>=%s ORDER BY node_id',(cutoff,))
            return tuple(r[0] for r in cur.fetchall())

    def close(self): self.con.close()
