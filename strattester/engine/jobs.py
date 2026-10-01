from __future__ import annotations
from dataclasses import dataclass,replace
from enum import Enum
import time,uuid
class JobState(str,Enum):
    PENDING='PENDING'; BLOCKED='BLOCKED'; READY='READY'; LEASED='LEASED'; RUNNING='RUNNING'
    CHECKPOINTED='CHECKPOINTED'; RETRYABLE='RETRYABLE'; FAILED='FAILED'; COMPLETE='COMPLETE'; CANCELLED='CANCELLED'
@dataclass(frozen=True)
class Job:
    id:str
    job_type:str
    symbol:str|None=None
    strategy_id:str|None=None
    strategy_version:str|None=None
    config_hash:str=''
    state:JobState=JobState.PENDING
    attempts:int=0
    lease_owner:str|None=None
    lease_until:float|None=None
    checkpoint:str|None=None
    error:str|None=None
    @classmethod
    def new(cls,job_type,**kw): return cls(str(uuid.uuid4()),job_type,**kw)
    def with_state(self,state,**kw): return replace(self,state=state,**kw)
    def recover_stale(self,now=None):
        now=time.time() if now is None else now
        if self.state in (JobState.LEASED,JobState.RUNNING) and self.lease_until is not None and self.lease_until<now:
            return replace(self,state=JobState.RETRYABLE,lease_owner=None,lease_until=None,error='stale lease')
        return self
