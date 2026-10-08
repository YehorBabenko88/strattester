from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import time
import json
import os
import threading
from pathlib import Path
from .sqlite_store import Candle
from .bybit_client import BybitAccessError
from .errors import (
    DatasetUnavailableError,
    MarketDataAccessError,
    RetryableMarketDataError,
    MarketDataIntegrityError,
)
from .timeframes import (
    aligned_window,
    timeframe_ms,
)

class SyncState(str,Enum):
    UNKNOWN='UNKNOWN'; CHECKING='CHECKING'; PARTIAL='PARTIAL'; SYNCING='SYNCING'
    VALIDATING='VALIDATING'; READY='READY'; DEGRADED='DEGRADED'; RETRYABLE='RETRYABLE'; UNAVAILABLE='UNAVAILABLE'; REPAIR_REQUIRED='REPAIR_REQUIRED'

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

def _bybit_interval(timeframe:str)->str:
    tf=str(timeframe).lower()
    mapping={
        '1m':'1','3m':'3','5m':'5','15m':'15','30m':'30',
        '1h':'60','2h':'120','4h':'240','6h':'360','12h':'720',
        '1d':'D',
    }
    return mapping.get(tf, timeframe)

_journal_thread_guard=threading.Lock()
_journal_thread_locks={}

def _thread_lock_for_journal(path):
    key=str(path.resolve())
    with _journal_thread_guard:
        return _journal_thread_locks.setdefault(key,threading.RLock())

class SyncEngine:
    def __init__(self,store,client,clock_ms=None,funding_schedules=None,funding_drift_journal=None):
        self.store=store; self.client=client; self.clock_ms=clock_ms or (lambda:int(time.time()*1000))
        # Explicit, independently verified per-symbol (interval_ms, anchor_ms).
        # Never infer funding cadence from the research candle timeframe.
        self.funding_schedules=dict(funding_schedules or {})
        self.funding_drift_journal=Path(funding_drift_journal) if funding_drift_journal is not None else None

    def read_funding_drift_alerts(self):
        """Recover latest complete observation, including across journal rotation.

        If a crash happens between rotation and the next append, the previous
        generation still contains the last durable observation.
        """
        path=self.funding_drift_journal
        if path is None:
            return {'state':SyncState.UNKNOWN,'changes':{},'observed_at_ms':None}
        seen=False
        for candidate in (path,path.with_name(path.name+'.1')):
            try:
                with candidate.open('rb') as stream:
                    stream.seek(0,os.SEEK_END)
                    size=stream.tell()
                    seen=True
                    stream.seek(max(0,size-1048576))
                    data=stream.read()
                if size>1048576:
                    # The bounded tail may start mid-record. Discard only
                    # that partial prefix, not a complete first line.
                    data=data.split(b'\n',1)[-1]
                if not data.endswith(b'\n'):
                    data=data.rsplit(b'\n',1)[0]+b'\n' if b'\n' in data else b''
                for line in reversed(data.splitlines()):
                    try:
                        record=json.loads(line.decode('utf-8'))
                        if not isinstance(record,dict) or not isinstance(record.get('changes'),dict):
                            continue
                        observed=record.get('observed_at_ms')
                        if not isinstance(observed,int) or isinstance(observed,bool) or observed<0:
                            continue
                        return {'state':SyncState.REPAIR_REQUIRED if record['changes'] else SyncState.READY,
                                'changes':record['changes'],'observed_at_ms':observed}
                    except (ValueError,UnicodeError,TypeError):
                        continue
            except FileNotFoundError:
                # Rotation can move a generation between path discovery and
                # opening it. Check the next generation rather than treating
                # this normal race as corruption.
                continue
            except OSError as exc:
                return {'state':SyncState.RETRYABLE,'changes':{},
                        'message':f'funding drift journal recovery failed: {exc}'}
        if not seen:
            # A durable marker is written only after a journal record has
            # been fsynced. Unlike the lock file, it cannot be created by
            # an ordinary first check that has never persisted an event.
            marker=path.with_name(path.name+'.initialized')
            try:
                with marker.open('rb') as initialized:
                    initialized.read(1)
            except FileNotFoundError:
                return {'state':SyncState.UNKNOWN,'changes':{},'observed_at_ms':None}
            except OSError as exc:
                return {'state':SyncState.RETRYABLE,'changes':{},
                        'message':f'funding drift initialization marker inaccessible: {exc}'}
            return {'state':SyncState.RETRYABLE,'changes':{},
                    'message':'funding drift journal missing after prior durable record'}
        return {'state':SyncState.RETRYABLE,'changes':{},
                'message':'funding drift journal has no valid complete record'}

    def _funding_journal_lock(self):
        """Cross-process lock on a separate stable file (also across rotation)."""
        from contextlib import contextmanager
        @contextmanager
        def locked():
            path=self.funding_drift_journal
            path.parent.mkdir(parents=True,exist_ok=True)
            lock_path=path.with_name(path.name+'.lock')
            # Windows byte-range locks are process-wide but overlapping
            # attempts from threads in the same process can fail immediately.
            # Pair OS locks with a per-path thread lock.
            with _thread_lock_for_journal(lock_path):
                with lock_path.open('a+b') as stream:
                    if os.name=='nt':
                        import msvcrt
                        # Never read or initialize the lock byte before
                        # acquiring the Windows byte-range lock: another
                        # process may already hold it, and that read raises
                        # PermissionError rather than waiting.
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(),msvcrt.LK_LOCK,1)
                        try:
                            yield
                        finally:
                            stream.seek(0)
                            msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
                        try:
                            yield
                        finally:
                            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        return locked()

    def check_current_funding_intervals(self):
        """Compare live Bybit metadata with verified schedules without mutation.

        A mismatch is a review signal, not evidence that historical intervals
        should be rewritten. Historical multi-segment schedules are supported
        by comparing only the last explicitly verified segment.
        """
        try:
            current=self.client.fetch_current_funding_intervals()
            if not isinstance(current,dict):
                raise ValueError('invalid current funding metadata')
        except Exception as exc:
            return {'state':SyncState.RETRYABLE,'message':str(exc),'changes':{}}
        changes={}
        for symbol,schedule in self.funding_schedules.items():
            if symbol not in current:
                changes[symbol]={'state':'MISSING','verified_interval_ms':None,'current_interval_ms':None}
                continue
            try:
                if (isinstance(schedule,(list,tuple)) and
                        (len(schedule)!=2 or any(isinstance(x,(list,tuple,dict)) for x in schedule))):
                    if not schedule:
                        raise ValueError('empty schedule history')
                    interval=int(schedule[-1][1])
                else:
                    interval=int(schedule[0])
                observed=current[symbol]
                if isinstance(observed,bool) or not isinstance(observed,int) or observed<=0:
                    raise ValueError('invalid current funding interval')
            except (TypeError,ValueError,IndexError,KeyError) as exc:
                changes[symbol]={'state':'INVALID','message':str(exc)}
                continue
            if interval!=observed:
                changes[symbol]={
                    'state':'CHANGED',
                    'verified_interval_ms':interval,
                    'current_interval_ms':observed,
                }
        if self.funding_drift_journal is not None:
            # Persist resolution as an empty change set. This ensures old
            # warnings do not reappear as active after a clean restart.
            # Avoid recording identical alerts on every polling cycle.
            # After a reboot the last complete record remains authoritative
            # for deduplication; no in-memory cache is required.
            try:
                lock_context=self._funding_journal_lock()
                with lock_context:
                    return self._persist_funding_drift_locked(changes)
            except OSError as exc:
                return {'state':SyncState.RETRYABLE,'message':f'funding drift lock failed: {exc}','changes':changes}
        return {'state':SyncState.REPAIR_REQUIRED if changes else SyncState.READY,
                'message':'funding metadata requires review' if changes else '',
                'changes':changes}

    @staticmethod
    def _ensure_funding_marker(path):
        """Create or repair a durable marker after a complete journal event."""
        marker=path.with_name(path.name+'.initialized')
        if marker.exists():
            # An interrupted first write can leave an empty or partial marker.
            # The journal event has already been fsynced by the caller.
            # Never load an unbounded marker into memory: a damaged file
            # may have grown far beyond its expected two-byte payload.
            with marker.open('rb') as initialized:
                if initialized.read(3)==b'1\n':
                    return
            with marker.open('wb') as initialized:
                initialized.write(b'1\n')
                initialized.flush()
                os.fsync(initialized.fileno())
            return
        with marker.open('xb') as initialized:
            initialized.write(b'1\n')
            initialized.flush()
            os.fsync(initialized.fileno())

    def _persist_funding_drift_locked(self,changes):
        previous=self.read_funding_drift_alerts()
        if previous['state'] is SyncState.RETRYABLE:
            return {'state':SyncState.RETRYABLE,
                    'message':previous.get('message','funding drift journal unavailable'),
                    'changes':changes}
        if previous['state'] in (SyncState.REPAIR_REQUIRED,SyncState.READY) and previous['changes']==changes:
            # An interrupted marker creation must be retried even if the
            # journal already contains the latest observation.
            path=self.funding_drift_journal
            marker=path.with_name(path.name+'.initialized')
            try:
                self._ensure_funding_marker(path)
            except OSError as exc:
                return {'state':SyncState.RETRYABLE,'changes':changes,
                        'message':f'funding drift initialization marker failed: {exc}'}
            # A torn trailing record requires a new durable snapshot, even
            # when the last complete event matches the current observation.
            path=self.funding_drift_journal
            incomplete=False
            active_has_data=False
            try:
                if path.exists():
                    with path.open('rb') as stream:
                        stream.seek(0,os.SEEK_END)
                        size=stream.tell()
                        active_has_data=size>0
                        if size:
                            stream.seek(-1,os.SEEK_END)
                            incomplete=stream.read(1)!=b'\n'
            except OSError as exc:
                return {'state':SyncState.RETRYABLE,'changes':changes,
                        'message':f'funding drift journal inspection failed: {exc}'}
            # An empty active file after interrupted rotation is not a
            # durable duplicate of the valid event recovered from backup.
            if active_has_data and not incomplete:
                return {'state':SyncState.REPAIR_REQUIRED if changes else SyncState.READY,
                        'message':'funding metadata requires review' if changes else '',
                        'changes':changes}
        if previous['state'] is SyncState.UNKNOWN and not changes:
            # No prior event is expected on a clean first check. Do not
            # create a journal or marker until a drift event is observed.
            return {'state':SyncState.READY,'message':'','changes':{}}
        try:
            # Append-only evidence: never overwrite or alter market data.
            # Flush and fsync so a completed check survives a reboot.
            record={'observed_at_ms':int(self.clock_ms()),'changes':changes}
            path=self.funding_drift_journal
            path.parent.mkdir(parents=True,exist_ok=True)
            # Keep one previous journal generation for recovery while
            # bounding growth. Rotation happens before a new append.
            max_bytes=1024*1024
            if path.exists():
                # A crash may leave a partial JSON record without a newline.
                # Never append onto that fragment: rotate it to preserve
                # evidence and start a fresh, independently readable record.
                with path.open('rb') as existing:
                    existing.seek(0,os.SEEK_END)
                    size=existing.tell()
                    if size:
                        existing.seek(-1,os.SEEK_END)
                        incomplete=existing.read(1)!=b'\n'
                    else:
                        incomplete=False
                if size>=max_bytes or incomplete:
                    os.replace(path,path.with_name(path.name+'.1'))
            with path.open('a',encoding='utf-8') as journal:
                journal.write(json.dumps(record,sort_keys=True)+'\n')
                journal.flush()
                os.fsync(journal.fileno())
            # Persist an explicit initialization marker after the first
            # durable event, so disappearance of both generations is visible.
            marker=path.with_name(path.name+'.initialized')
            self._ensure_funding_marker(path)
        except OSError as exc:
            return {
                'state':SyncState.RETRYABLE,
                'message':f'funding drift journal write failed: {exc}',
                'changes':changes,
            }

        return {'state':SyncState.REPAIR_REQUIRED if changes else SyncState.READY,
                'message':'funding metadata requires review' if changes else '',
                'changes':changes}

    def _step(self,req):
        return timeframe_ms(req.timeframe)

    def _ranges(self,req,step=None):
        step=step or self._step(req)
        cov=self.store.coverage(req.symbol,req.dataset,req.timeframe,step)
        ranges=[]
        if cov.earliest is None:return [(req.start_ms,req.end_ms)]
        if req.start_ms<cov.earliest:ranges.append((req.start_ms,min(req.end_ms,cov.earliest-step)))
        ranges.extend((max(req.start_ms,g.start),min(req.end_ms,g.end)) for g in cov.gaps if g.end>=req.start_ms and g.start<=req.end_ms)
        if cov.latest+step<=req.end_ms:ranges.append((max(req.start_ms,cov.latest+step),req.end_ms))
        return [(a,b) for a,b in ranges if a<=b]

    def _sync_rows(self,req,start,end):
        step=self._step(req)
        if req.dataset=='candles':
            rows=self.client.fetch_klines(req.symbol,start,end,_bybit_interval(req.timeframe))
            accepted=[]
            for row in rows:
                ts=int(row[0])
                if start<=ts<=req.end_ms and ts+step<=self.clock_ms():
                    accepted.append(Candle(req.symbol,req.timeframe,ts,float(row[1]),float(row[2]),float(row[3]),float(row[4]),float(row[5]),float(row[6]) if len(row)>6 else None,True))
            return self.store.upsert_candles(accepted),rows
        if req.dataset in ('mark_price','index_price','premium_index'):
            method={'mark_price':'fetch_mark_klines','index_price':'fetch_index_klines','premium_index':'fetch_premium_klines'}[req.dataset]
            rows=getattr(self.client,method)(req.symbol,start,end,_bybit_interval(req.timeframe))
            closed=[r for r in rows if start<=int(r[0])<=req.end_ms and int(r[0])+step<=self.clock_ms()]
            return self.store.upsert_price_klines(req.dataset,req.symbol,closed,req.timeframe),rows
        if req.dataset=='open_interest':
            interval={'5m':'5min','15m':'15min','30m':'30min','1h':'1h','4h':'4h','1d':'1d'}.get(req.timeframe,req.timeframe)
            rows=self.client.fetch_open_interest(req.symbol,start,end,interval)
            def ts(r):
                v=r.get('timestamp') if r.get('timestamp') is not None else r.get('time')
                if v is None:raise ValueError('open-interest row missing timestamp')
                return int(v)
            closed=[r for r in rows if start<=ts(r)<=req.end_ms and ts(r)+step<=self.clock_ms()]
            return self.store.upsert_open_interest(req.symbol,closed,req.timeframe),rows
        if req.dataset=='funding':
            rows=self.client.fetch_funding(req.symbol,start,end)
            filtered=[r for r in rows if start<=int(r.get('fundingRateTimestamp'))<=req.end_ms and int(r.get('fundingRateTimestamp'))<=self.clock_ms()]
            return self.store.upsert_funding(req.symbol,filtered),rows
        if req.dataset=='long_short_ratio':
            period={'5m':'5min','15m':'15min','30m':'30min','1h':'1h','4h':'4h','1d':'1d'}.get(req.timeframe,req.timeframe)
            rows=self.client.fetch_long_short_ratio(req.symbol,start,end,period)
            filtered=[r for r in rows if start<=int(r.get('timestamp'))<=req.end_ms and int(r.get('timestamp'))+step<=self.clock_ms()]
            return self.store.upsert_long_short_ratio(req.symbol,filtered,req.timeframe),rows
        if req.dataset=='public_trade_aggregates':
            raise RuntimeError('historical public trades require archive provider; recent REST trades are not a historical substitute')
        raise ValueError('unsupported dataset')

    def _funding_ranges(self,req,step):
        # Query only the scheduled timestamps in this segment. Global
        # coverage gaps cannot be reused across cadence transitions.
        result=[]
        for chunk_start in range(req.start_ms,req.end_ms+1,step*200):
            chunk_end=min(req.end_ms,chunk_start+step*199)
            present={
                int(row[0]) for row in self.store.connection.execute(
                    'SELECT funding_time FROM funding WHERE symbol=? AND funding_time BETWEEN ? AND ?',
                    (req.symbol,chunk_start,chunk_end),
                )
            }
            missing_start=None
            for ts in range(chunk_start,chunk_end+1,step):
                if ts not in present:
                    if missing_start is None:
                        missing_start=ts
                elif missing_start is not None:
                    result.append((missing_start,ts-step))
                    missing_start=None
            if missing_start is not None:
                result.append((missing_start,chunk_end))
        return result

    def _sync_funding(self,req):
        written=unchanged=rejected=0
        step=self._step(req)
        try:
            for start,end in self._funding_ranges(req,step):
                page_end=end
                while page_end>=start:
                    rows=self.client.fetch_funding(req.symbol,start,page_end)
                    if not rows:
                        break
                    timestamps=[]
                    valid=[]
                    for row in rows:
                        ts=int(row['fundingRateTimestamp'])
                        # An unexpected event timestamp means the declared
                        # schedule may be stale or the response is malformed.
                        # Reject the entire page atomically: do not persist
                        # a subset and silently mark the range complete.
                        if (ts-req.start_ms)%step:
                            raise MarketDataIntegrityError(
                                'funding timestamp conflicts with verified schedule'
                            )
                        if ts<start or ts>page_end:
                            raise MarketDataIntegrityError(
                                'funding page contains timestamp outside requested range'
                            )
                        if ts>self.clock_ms():
                            raise MarketDataIntegrityError(
                                'funding page contains a future event'
                            )
                        timestamps.append(ts)
                        valid.append(row)
                    if len(set(timestamps))!=len(timestamps):
                        raise MarketDataIntegrityError(
                            'funding page contains duplicate event timestamps'
                        )
                    stats=self.store.upsert_funding(req.symbol,valid)
                    written+=stats.accepted
                    unchanged+=stats.unchanged
                    rejected+=stats.rejected
                    minimum=min(timestamps)
                    if minimum<=start:
                        break
                    next_end=minimum-1
                    if next_end>=page_end:
                        break
                    page_end=next_end
            remaining=self._funding_ranges(req,step)
            return SyncResult(
                SyncState.PARTIAL if remaining else SyncState.READY,
                written,unchanged,rejected,
                'requested funding events remain incomplete' if remaining else '',
            )
        except DatasetUnavailableError as exc:
            return SyncResult(SyncState.UNAVAILABLE,written,unchanged,rejected,str(exc))
        except (MarketDataAccessError,BybitAccessError) as exc:
            return SyncResult(SyncState.DEGRADED,written,unchanged,rejected,str(exc))
        except Exception as exc:
            return SyncResult(SyncState.RETRYABLE,written,unchanged,rejected,str(exc))

    def _sync_funding_segments(self,req,segments):
        # Each (effective_from_ms, interval_ms, anchor_ms) is independently
        # verified. Boundaries are half-open; the next segment owns its start.
        try:
            if not segments:
                raise ValueError('empty funding schedule history')
            normalized=[]
            for segment in segments:
                if not isinstance(segment,(tuple,list)) or len(segment)!=3:
                    raise ValueError('funding segment must contain start, interval and anchor')
                since,interval,anchor=map(int,segment)
                if since<0 or interval<=0 or interval%60000 or not 0<=anchor<interval:
                    raise ValueError('invalid funding segment')
                if normalized and since<=normalized[-1][0]:
                    raise ValueError('funding segments must have strictly increasing starts')
                normalized.append((since,interval,anchor))
            if req.end_ms<req.start_ms:
                raise ValueError('invalid requested funding window')
            if req.start_ms<0:
                raise ValueError('funding window cannot start before epoch')
            if req.start_ms<normalized[0][0]:
                return SyncResult(SyncState.UNAVAILABLE,message='funding schedule does not cover requested history')
            # A segment's effective start must be a scheduled event boundary.
            # Otherwise the boundary could conceal an event or assign it to
            # the wrong cadence. Require independent schedule correction.
            for since,interval,anchor in normalized:
                if (since-anchor)%interval:
                    raise ValueError('funding segment start is not aligned with its schedule')
        except (TypeError,ValueError,OverflowError) as exc:
            return SyncResult(SyncState.REPAIR_REQUIRED,message=str(exc))

        totals=[0,0,0]
        found_event=False
        for i,(since,interval,anchor) in enumerate(normalized):
            start=max(int(req.start_ms),since)
            end=int(req.end_ms)
            if i+1<len(normalized):
                end=min(end,normalized[i+1][0]-1)
            if end<start:
                continue
            first=anchor+((start-anchor+interval-1)//interval)*interval
            last=anchor+((end-anchor)//interval)*interval
            if first>last:
                continue
            found_event=True
            if last>int(self.clock_ms()):
                return SyncResult(SyncState.PARTIAL,*totals,
                                  message='requested funding window includes future events')
            part=self._sync_funding(DataRequirement(
                req.symbol,'funding',f'{interval//60000}m',first,last
            ))
            totals[0]+=part.written
            totals[1]+=part.unchanged
            totals[2]+=part.rejected
            if part.state is not SyncState.READY:
                return SyncResult(part.state,*totals,message=part.message)
        if not found_event:
            return SyncResult(SyncState.REPAIR_REQUIRED,*totals,
                              message='no scheduled funding event in requested window')
        return SyncResult(SyncState.READY,*totals)

    def sync_requirement(self,req:DataRequirement)->SyncResult:
        if req.dataset == 'funding':
            schedule=self.funding_schedules.get(req.symbol)
            if schedule is None:
                return SyncResult(
                    SyncState.UNAVAILABLE,
                    message='funding event coverage requires a verified instrument-specific schedule',
                )
            # A single interval cannot represent historical changes. Reject
            # ambiguous multi-segment configurations instead of silently
            # treating their events as a uniform time series.
            if (isinstance(schedule,(list,tuple)) and
                    (len(schedule)!=2 or any(isinstance(x,(list,tuple,dict)) for x in schedule))):
                return self._sync_funding_segments(req,schedule)
            try:
                interval,anchor=schedule
                interval=int(interval)
                anchor=int(anchor)
                if interval<=0 or anchor<0 or anchor>=interval:
                    raise ValueError('invalid funding schedule')
                first=anchor+((int(req.start_ms)-anchor+interval-1)//interval)*interval
                last=anchor+((int(req.end_ms)-anchor)//interval)*interval
                if first>last:
                    return SyncResult(SyncState.REPAIR_REQUIRED,message='no scheduled funding event in requested window')
                # A scheduled event in the future is not missing history and
                # must never be accepted as READY, even if a cached row exists.
                if last>int(self.clock_ms()):
                    return SyncResult(SyncState.PARTIAL,message='requested funding window includes future events')
                # Reuse the gap-repair/pagination engine with the *event*
                # interval, not the candle timeframe. The funding table
                # deliberately has no timeframe dimension.
                req=DataRequirement(req.symbol,'funding',f'{interval//60000}m',first,last)
                if interval%60000:
                    return SyncResult(SyncState.REPAIR_REQUIRED,message='funding schedule must use whole-minute intervals')
            except (TypeError,ValueError,OverflowError) as exc:
                return SyncResult(SyncState.REPAIR_REQUIRED,message=f'invalid funding schedule: {exc}')
            return self._sync_funding(req)
        window=aligned_window(
            req.start_ms,
            req.end_ms,
            req.timeframe,
        )

        if window is None:
            return SyncResult(
                SyncState.REPAIR_REQUIRED,
                message=(
                    'requested window contains no complete '
                    f'{req.timeframe} observation'
                ),
            )

        aligned_start,aligned_end=window

        if (
            aligned_start!=req.start_ms
            or aligned_end!=req.end_ms
        ):
            req=DataRequirement(
                req.symbol,
                req.dataset,
                req.timeframe,
                aligned_start,
                aligned_end,
            )

        if req.dataset=='public_trade_aggregates':
            return SyncResult(SyncState.REPAIR_REQUIRED,message='historical public trades require archive provider; recent REST trades are not a historical substitute')
        if req.dataset not in ('candles','mark_price','index_price','premium_index','open_interest','funding','long_short_ratio'):
            return SyncResult(SyncState.REPAIR_REQUIRED,message='unsupported dataset')
        written=unchanged=rejected=0
        step=self._step(req)
        try:
            for start,end in self._ranges(req,step):
                page_end=end
                while page_end>=start:
                    stats,rows=self._sync_rows(req,start,page_end)
                    written+=stats.accepted; unchanged+=stats.unchanged; rejected+=stats.rejected
                    if not rows:
                        # Empty pages are not evidence of coverage. Leave the
                        # requested range missing so the result cannot become READY.
                        break
                    timestamps=[]
                    for row in rows:
                        if isinstance(row,dict):
                            key='fundingRateTimestamp' if req.dataset=='funding' else 'timestamp'
                            value=row.get(key) if row.get(key) is not None else row.get('time')
                            if value is None:raise ValueError('dataset row missing timestamp')
                            timestamps.append(int(value))
                        else: timestamps.append(int(row[0]))
                    min_ts=min(timestamps)
                    if min_ts<=start:break
                    next_end=min_ts-step
                    if next_end>=page_end:break
                    page_end=next_end
            remaining=self._ranges(req,step)
            state=SyncState.READY if not remaining else SyncState.PARTIAL
            message='' if not remaining else 'requested history remains incomplete'
            return SyncResult(state,written,unchanged,rejected,message)
        except DatasetUnavailableError as exc:
            return SyncResult(
                SyncState.UNAVAILABLE,
                written,
                unchanged,
                rejected,
                str(exc),
            )
        except (MarketDataAccessError, BybitAccessError) as exc:
            return SyncResult(
                SyncState.DEGRADED,
                written,
                unchanged,
                rejected,
                str(exc),
            )
        except (
            RetryableMarketDataError,
            MarketDataIntegrityError,
        ) as exc:
            return SyncResult(
                SyncState.RETRYABLE,
                written,
                unchanged,
                rejected,
                str(exc),
            )
        except Exception as exc:
            # Unknown failures fail closed as retryable.
            # Classification must never depend on exception
            # class names or human-readable message text.
            return SyncResult(
                SyncState.RETRYABLE,
                written,
                unchanged,
                rejected,
                str(exc),
            )
