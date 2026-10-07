from strattester.persistence.postgres_state_store import PostgresStateStore

class Cursor:
    def __init__(self,con):self.con=con;self.rowcount=0;self.result=None
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def execute(self,sql,args=None):
        s=" ".join(sql.split());self.rowcount=0;self.result=None
        if s.startswith("SELECT holder,epoch,expires_at FROM strattester_brain_lease WHERE singleton=TRUE"):
            self.result=self.con.lease
        elif s.startswith("UPDATE strattester_brain_lease SET holder"):
            holder,epoch,expires=args;self.con.lease=(holder,epoch,expires);self.rowcount=1
        elif s.startswith("UPDATE strattester_brain_lease SET expires_at"):
            exp,holder,epoch,now=args
            if self.con.lease and self.con.lease[0]==holder and self.con.lease[1]==epoch and self.con.lease[2]>now:
                self.con.lease=(holder,epoch,exp);self.rowcount=1
        elif s.startswith("SELECT sequence,event_id,payload_hash,payload FROM strattester_learning_log"):
            self.result=self.con.log.get(tuple(args))
        elif s.startswith("INSERT INTO strattester_learning_log"):
            event,decision,horizon,payload,digest,_=args;self.con.seq+=1
            import json
            self.con.log[(decision,horizon)]=(self.con.seq,event,digest,json.loads(payload));self.result=(self.con.seq,);self.rowcount=1
        elif s.startswith("INSERT INTO strattester_learning_events"):
            event,decision,horizon,_,_=args
            key=(decision,horizon)
            if key not in self.con.events:
                self.con.events[key]=event;self.rowcount=1
        elif s.startswith("SELECT 1 FROM strattester_learning_events"):
            self.result=(1,) if tuple(args) in self.con.events else None
    def fetchone(self):return self.result

class Con:
    def __init__(self):self.lease=('',0,0);self.events={};self.log={};self.seq=0
    def cursor(self):return Cursor(self)
    def commit(self):pass
    def rollback(self):pass

def test_brain_lease_fences_second_holder_until_expiry():
    s=PostgresStateStore(Con())
    a=s.acquire_brain_lease("a",10,now=0)
    assert a["epoch"]==1
    assert s.acquire_brain_lease("b",10,now=5) is None
    b=s.acquire_brain_lease("b",10,now=11)
    assert b["epoch"]==2 and b["holder"]=="b"

def test_stale_epoch_cannot_renew_after_failover():
    s=PostgresStateStore(Con())
    a=s.acquire_brain_lease("a",10,now=0)
    s.acquire_brain_lease("b",10,now=11)
    assert not s.renew_brain_lease("a",a["epoch"],10,now=12)

def test_learning_claim_is_exactly_once_per_decision_horizon():
    s=PostgresStateStore(Con())
    assert s.claim_learning_event("e1","d1","1h",now=1)
    assert not s.claim_learning_event("e2","d1","1h",now=2)
    assert s.learning_event_applied("d1","1h")


def test_same_live_holder_renews_without_epoch_increment():
    s=PostgresStateStore(Con())
    a=s.acquire_brain_lease("a",10,now=0)
    again=s.acquire_brain_lease("a",10,now=5)
    assert a["epoch"]==again["epoch"]==1

def test_invalid_brain_lease_parameters_fail_closed():
    s=PostgresStateStore(Con())
    for holder,seconds in [("",10),("a",0),("a",-1)]:
        try:s.acquire_brain_lease(holder,seconds,now=0)
        except ValueError:pass
        else:raise AssertionError("invalid lease accepted")


def test_immutable_learning_log_is_idempotent_and_detects_collision():
    s=PostgresStateStore(Con());payload={"utility":1.0,"attribution":{"m":.5}}
    a,new=s.append_learning_log("e1","d1","1h",payload,now=1)
    b,new2=s.append_learning_log("e1","d1","1h",payload,now=2)
    assert new and not new2 and a["sequence"]==b["sequence"]==1
    try:s.append_learning_log("e1","d1","1h",{"utility":-9},now=3)
    except ValueError as e:assert "collision" in str(e)
    else:raise AssertionError("conflicting durable learning event accepted")
