from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import time
from .sqlite_store import Candle

class SyncState(str,Enum):
    UNKNOWN='UNKNOWN'; CHECKING='CHECKING'; PARTIAL='PARTIAL'; SYNCING='SYNCING'
    VALIDATING='VALIDATING'; READY='READY'; DEGRADED='DEGRADED'; RETRYABLE='RETRYABLE'; REPAIR_REQUIRED='REPAIR_REQUIRED'

@dataclass(frozen=True)
class DataRequirement:
    symbol:str
    dataset:str='candles'
    timeframe:str='1m'
    start_ms:int=0
    end_ms:int=0

@dataclass(frozen=True)
class SyncResult:
    state:SyncState
    written:int=0
    unchanged:int=0
    rejected:int=0
    message:str=''

class SyncEngine:
    def __init__(self,store,client,clock_ms=None):
        self.store=store; self.client=client; self.clock_ms=clock_ms or (lambda:int(time.time()*1000))

    def _ranges(self,req,step=60_000):
        cov=self.store.coverage(req.symbol,req.dataset,req.timeframe,step)
        ranges=[]
        if cov.earliest is None: return [(req.start_ms,req.end_ms)]
        if req.start_ms<cov.earliest: ranges.append((req.start_ms,cov.earliest-step))
        ranges.extend((max(req.start_ms,g.start),min(req.end_ms,g.end)) for g in cov.gaps if g.end>=req.start_ms and g.start<=req.end_ms)
        if cov.latest+step<=req.end_ms: ranges.append((cov.latest+step,req.end_ms))
        return [(a,b) for a,b in ranges if a<=b]

    def sync_requirement(self,req:DataRequirement)->SyncResult:
        if req.dataset!='candles': return SyncResult(SyncState.REPAIR_REQUIRED,message='unsupported dataset')
        written=unchanged=rejected=0
        try:
            for start,end in self._ranges(req):
                page_end=end
                while page_end>=start:
                    rows=self.client.fetch_klines(req.symbol,start,page_end,'1')
                    if not rows: break
                    candles=[]
                    timestamps=[int(row[0]) for row in rows]
                    min_ts=min(timestamps)
                    for row in rows:
                        ts=int(row[0])
                        if ts<start or ts>req.end_ms or ts+60_000>self.clock_ms(): continue
                        candles.append(Candle(req.symbol,req.timeframe,ts,float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5]),float(row[6]) if len(row)>6 else None,True))
                    stats=self.store.upsert_candles(candles)
                    written+=stats.accepted; unchanged+=stats.unchanged; rejected+=stats.rejected
                    if min_ts<=start: break
                    next_end=min_ts-60_000
                    if next_end>=page_end: break
                    page_end=next_end
            remaining=self._ranges(req)
            state=SyncState.READY if not remaining else SyncState.PARTIAL
            return SyncResult(state,written,unchanged,rejected)
        except Exception as exc:
            name=exc.__class__.__name__
            state=SyncState.DEGRADED if name=='BybitAccessError' else SyncState.RETRYABLE
            return SyncResult(state,written,unchanged,rejected,str(exc))
