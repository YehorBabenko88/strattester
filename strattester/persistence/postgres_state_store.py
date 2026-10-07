from __future__ import annotations
import json,time,hashlib
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
            cur.execute("ALTER TABLE strattester_nodes ADD COLUMN IF NOT EXISTS generation BIGINT NOT NULL DEFAULT 0")
            cur.execute('''CREATE TABLE IF NOT EXISTS strattester_brain_lease(
                singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
                holder TEXT NOT NULL, epoch BIGINT NOT NULL, expires_at DOUBLE PRECISION NOT NULL)''')
            cur.execute("""INSERT INTO strattester_brain_lease(singleton,holder,epoch,expires_at)
                VALUES(TRUE,'',0,0) ON CONFLICT(singleton) DO NOTHING""")
            cur.execute('''CREATE TABLE IF NOT EXISTS strattester_learning_events(
                event_id TEXT PRIMARY KEY, decision_id TEXT NOT NULL, horizon TEXT NOT NULL,
                applied_at DOUBLE PRECISION NOT NULL, meta JSONB NOT NULL DEFAULT '{}'::jsonb,
                status TEXT NOT NULL DEFAULT 'APPLIED', claimed_at DOUBLE PRECISION,
                UNIQUE(decision_id,horizon))''')
            cur.execute("ALTER TABLE strattester_learning_events ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'APPLIED'")
            cur.execute('ALTER TABLE strattester_learning_events ADD COLUMN IF NOT EXISTS claimed_at DOUBLE PRECISION')
            cur.execute('''CREATE TABLE IF NOT EXISTS strattester_learning_log(
                sequence BIGSERIAL PRIMARY KEY,event_id TEXT NOT NULL UNIQUE,
                decision_id TEXT NOT NULL,horizon TEXT NOT NULL,payload JSONB NOT NULL,
                payload_hash TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL,
                UNIQUE(decision_id,horizon))''')
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

    def compare_and_swap_job(self,expected,replacement):
        try:
            with self.con.cursor() as cur:
                cur.execute('SELECT payload FROM strattester_jobs WHERE id=%s FOR UPDATE',(expected.id,))
                row=cur.fetchone()
                if row is None:
                    self.con.rollback(); return False
                current=self._decode(row[0])
                if current.state!=expected.state or current.lease_token!=expected.lease_token or current.target_node!=expected.target_node or current.lease_owner!=expected.lease_owner:
                    self.con.rollback(); return False
                cur.execute('UPDATE strattester_jobs SET payload=%s::jsonb WHERE id=%s',
                            (json.dumps(self._encode(replacement)),expected.id))
            self.con.commit(); return True
        except Exception:
            self.con.rollback(); raise

    def lease_valid(self,job_id,owner,lease_token,now=None):
        now=time.time() if now is None else float(now)
        job=self.get_job(job_id)
        return bool(job and job.lease_owner==owner and job.lease_token==lease_token
                    and job.state in _ACTIVE and (job.lease_until is None or job.lease_until>=now))

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

    def register_node_generation(self,node_id,now=None,meta=None):
        now=time.time() if now is None else float(now);payload=json.dumps(meta or {})
        try:
            with self.con.cursor() as cur:
                cur.execute('''INSERT INTO strattester_nodes(node_id,last_seen,meta,generation)
                    VALUES(%s,%s,%s::jsonb,1)
                    ON CONFLICT(node_id) DO UPDATE SET last_seen=excluded.last_seen,meta=excluded.meta,
                    generation=strattester_nodes.generation+1 RETURNING generation''',
                    (str(node_id),now,payload))
                generation=int(cur.fetchone()[0])
            self.con.commit();return generation
        except Exception:
            self.con.rollback();raise

    def heartbeat_node(self,node_id,now=None,meta=None,generation=None):
        now=time.time() if now is None else float(now);payload=json.dumps(meta or {})
        try:
            with self.con.cursor() as cur:
                if generation is None:
                    cur.execute('''INSERT INTO strattester_nodes(node_id,last_seen,meta)
                        VALUES(%s,%s,%s::jsonb)
                        ON CONFLICT(node_id) DO UPDATE SET last_seen=excluded.last_seen,meta=excluded.meta''',
                        (str(node_id),now,payload));ok=True
                else:
                    cur.execute('''UPDATE strattester_nodes SET last_seen=%s,meta=%s::jsonb
                        WHERE node_id=%s AND generation=%s AND last_seen<=%s''',
                        (now,payload,str(node_id),int(generation),now));ok=cur.rowcount==1
            self.con.commit();return ok
        except Exception:
            self.con.rollback(); raise

    def node_generation_valid(self,node_id,generation):
        if generation is None:return False
        with self.con.cursor() as cur:
            cur.execute('SELECT generation FROM strattester_nodes WHERE node_id=%s',(str(node_id),))
            row=cur.fetchone()
        return bool(row is not None and int(row[0])==int(generation))

    def execution_fence_valid(self,job_id,owner,lease_token,node_id,generation,now=None):
        return self.lease_valid(job_id,owner,lease_token,now=now) and self.node_generation_valid(node_id,generation)

    def live_nodes(self,stale_after=30,now=None):
        now=time.time() if now is None else float(now)
        cutoff=now-float(stale_after)
        with self.con.cursor() as cur:
            cur.execute('SELECT node_id FROM strattester_nodes WHERE last_seen>=%s ORDER BY node_id',(cutoff,))
            return tuple(r[0] for r in cur.fetchall())

    def _db_now(self,cur):
        cur.execute("SELECT EXTRACT(EPOCH FROM clock_timestamp())")
        return float(cur.fetchone()[0])

    def acquire_brain_lease(self,holder,lease_seconds=30,now=None):
        holder=str(holder);lease_seconds=float(lease_seconds)
        if not holder or lease_seconds<=0:raise ValueError("invalid brain lease request")
        try:
            with self.con.cursor() as cur:
                cur.execute('SELECT holder,epoch,expires_at FROM strattester_brain_lease WHERE singleton=TRUE FOR UPDATE')
                row=cur.fetchone()
                if row is None:raise RuntimeError("brain lease singleton missing")
                db_now=float(now) if now is not None else self._db_now(cur)
                if row[2]>db_now and row[0]!=holder:
                    self.con.rollback(); return None
                epoch=int(row[1])+(0 if row[0]==holder and row[2]>db_now else 1)
                expires=db_now+lease_seconds
                cur.execute('''UPDATE strattester_brain_lease
                    SET holder=%s,epoch=%s,expires_at=%s WHERE singleton=TRUE''',
                    (holder,epoch,expires))
            self.con.commit(); return {"holder":holder,"epoch":epoch,"expires_at":expires}
        except Exception:
            self.con.rollback(); raise

    def renew_brain_lease(self,holder,epoch,lease_seconds=30,now=None):
        holder=str(holder);epoch=int(epoch);lease_seconds=float(lease_seconds)
        if not holder or epoch<1 or lease_seconds<=0:raise ValueError("invalid brain lease renewal")
        try:
            with self.con.cursor() as cur:
                db_now=float(now) if now is not None else self._db_now(cur)
                cur.execute('''UPDATE strattester_brain_lease SET expires_at=%s
                    WHERE singleton=TRUE AND holder=%s AND epoch=%s AND expires_at>%s''',
                    (db_now+lease_seconds,holder,epoch,db_now))
                ok=cur.rowcount==1
            self.con.commit(); return ok
        except Exception:
            self.con.rollback(); raise

    def brain_lease(self):
        with self.con.cursor() as cur:
            cur.execute('SELECT holder,epoch,expires_at FROM strattester_brain_lease WHERE singleton=TRUE')
            row=cur.fetchone()
        return None if row is None else {"holder":row[0],"epoch":int(row[1]),"expires_at":float(row[2])}

    @staticmethod
    def _canonical_payload(payload):
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        return raw,hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def append_learning_log(self,event_id,decision_id,horizon,payload,now=None,brain_holder=None,brain_epoch=None):
        event_id=str(event_id);decision_id=str(decision_id);horizon=str(horizon)
        if not event_id or not decision_id or not horizon:raise ValueError("learning log identity required")
        raw,digest=self._canonical_payload(payload)
        try:
            with self.con.cursor() as cur:
                db_now=float(now) if now is not None else self._db_now(cur)
                if brain_holder is not None or brain_epoch is not None:
                    cur.execute('''SELECT 1 FROM strattester_brain_lease
                        WHERE singleton=TRUE AND holder=%s AND epoch=%s AND expires_at>%s FOR SHARE''',
                        (str(brain_holder),int(brain_epoch or 0),db_now))
                    if cur.fetchone() is None:
                        self.con.rollback();return None,False
                cur.execute('''SELECT sequence,event_id,payload_hash,payload FROM strattester_learning_log
                    WHERE decision_id=%s AND horizon=%s FOR UPDATE''',(decision_id,horizon))
                existing=cur.fetchone()
                if existing is not None:
                    if str(existing[1])!=event_id or str(existing[2])!=digest:
                        raise ValueError("learning log collision")
                    self.con.commit();return {"sequence":int(existing[0]),"event_id":str(existing[1]),"payload":existing[3]},False
                cur.execute('''INSERT INTO strattester_learning_log
                    (event_id,decision_id,horizon,payload,payload_hash,created_at)
                    VALUES(%s,%s,%s,%s::jsonb,%s,%s) RETURNING sequence''',
                    (event_id,decision_id,horizon,raw,digest,db_now))
                seq=int(cur.fetchone()[0])
            self.con.commit();return {"sequence":seq,"event_id":event_id,"payload":payload},True
        except Exception:
            self.con.rollback();raise

    def learning_log_after(self,sequence=0,limit=1000):
        sequence=int(sequence);limit=int(limit)
        if sequence<0 or not 1<=limit<=10000:raise ValueError("invalid learning log query")
        with self.con.cursor() as cur:
            cur.execute('''SELECT sequence,event_id,decision_id,horizon,payload,payload_hash
                FROM strattester_learning_log WHERE sequence>%s ORDER BY sequence LIMIT %s''',
                (sequence,limit))
            rows=cur.fetchall()
        return tuple({"sequence":int(r[0]),"event_id":r[1],"decision_id":r[2],
                      "horizon":r[3],"payload":r[4],"payload_hash":r[5]} for r in rows)

    def claim_learning_event(self,event_id,decision_id,horizon,now=None,meta=None):
        now=time.time() if now is None else float(now)
        try:
            with self.con.cursor() as cur:
                cur.execute('''INSERT INTO strattester_learning_events(event_id,decision_id,horizon,applied_at,meta)
                    VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING''',
                    (str(event_id),str(decision_id),str(horizon),now,json.dumps(meta or {})))
                claimed=cur.rowcount==1
            self.con.commit(); return claimed
        except Exception:
            self.con.rollback(); raise

    def brain_authority_valid(self,holder,epoch,now=None):
        holder=str(holder);epoch=int(epoch)
        if not holder or epoch<1:return False
        with self.con.cursor() as cur:
            db_now=float(now) if now is not None else self._db_now(cur)
            cur.execute('''SELECT 1 FROM strattester_brain_lease
                WHERE singleton=TRUE AND holder=%s AND epoch=%s AND expires_at>%s''',
                (holder,epoch,db_now))
            return cur.fetchone() is not None

    def begin_learning_event(self,event_id,decision_id,horizon,now=None,meta=None,brain_holder=None,brain_epoch=None):
        now=time.time() if now is None else float(now)
        try:
            with self.con.cursor() as cur:
                if brain_holder is not None or brain_epoch is not None:
                    db_now=float(now) if now is not None else self._db_now(cur)
                    cur.execute('''SELECT 1 FROM strattester_brain_lease
                        WHERE singleton=TRUE AND holder=%s AND epoch=%s AND expires_at>%s FOR SHARE''',
                        (str(brain_holder),int(brain_epoch or 0),db_now))
                    if cur.fetchone() is None:
                        self.con.rollback();return False
                cur.execute('''INSERT INTO strattester_learning_events
                    (event_id,decision_id,horizon,applied_at,meta,status,claimed_at)
                    VALUES(%s,%s,%s,%s,%s::jsonb,'CLAIMED',%s) ON CONFLICT DO NOTHING''',
                    (str(event_id),str(decision_id),str(horizon),0.0,json.dumps(meta or {}),now))
                claimed=cur.rowcount==1
            self.con.commit(); return claimed
        except Exception:
            self.con.rollback(); raise

    def complete_learning_event(self,event_id,now=None):
        now=time.time() if now is None else float(now)
        try:
            with self.con.cursor() as cur:
                cur.execute("""UPDATE strattester_learning_events SET status='APPLIED',applied_at=%s
                    WHERE event_id=%s AND status='CLAIMED'""",(now,str(event_id)))
                ok=cur.rowcount==1
            self.con.commit(); return ok
        except Exception:
            self.con.rollback(); raise

    def learning_event_status(self,event_id):
        with self.con.cursor() as cur:
            cur.execute('SELECT status FROM strattester_learning_events WHERE event_id=%s',(str(event_id),))
            row=cur.fetchone()
        return None if row is None else row[0]

    def pending_learning_events(self):
        with self.con.cursor() as cur:
            cur.execute("""SELECT event_id,decision_id,horizon FROM strattester_learning_events
                WHERE status='CLAIMED' ORDER BY claimed_at,event_id""")
            return tuple({"event_id":r[0],"decision_id":r[1],"horizon":r[2]} for r in cur.fetchall())

    def learning_event_applied(self,decision_id,horizon):
        with self.con.cursor() as cur:
            cur.execute('SELECT 1 FROM strattester_learning_events WHERE decision_id=%s AND horizon=%s',
                        (str(decision_id),str(horizon)))
            return cur.fetchone() is not None

    def close(self): self.con.close()
