from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import time
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

class SyncEngine:
    def __init__(self,store,client,clock_ms=None):
        self.store=store; self.client=client; self.clock_ms=clock_ms or (lambda:int(time.time()*1000))

    def _step(self,req):
        return timeframe_ms(req.timeframe)

    def _ranges(self,req,step=None):
        step=step or self._step(req)
        cov=self.store.coverage(req.symbol,req.dataset,req.timeframe,step)
        ranges=[]
        if cov.earliest is None:return [(req.start_ms,req.end_ms)]
        if req.start_ms<cov.earliest:ranges.append((req.start_ms,cov.earliest-step))
        ranges.extend((max(req.start_ms,g.start),min(req.end_ms,g.end)) for g in cov.gaps if g.end>=req.start_ms and g.start<=req.end_ms)
        if cov.latest+step<=req.end_ms:ranges.append((cov.latest+step,req.end_ms))
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

    def sync_requirement(self,req:DataRequirement)->SyncResult:
        # Funding is event-based, not a bar series. A candle timeframe
        # cannot establish which funding timestamps are expected. Until a
        # per-symbol funding schedule and event coverage validator exist,
        # fail closed instead of returning a misleading READY or repeatedly
        # requesting every missing candle-sized interval.
        if req.dataset == 'funding':
            return SyncResult(
                SyncState.UNAVAILABLE,
                message=(
                    'funding event coverage requires a verified '
                    'instrument-specific schedule; candle timeframe '
                    'must not be used as funding cadence'
                ),
            )
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
