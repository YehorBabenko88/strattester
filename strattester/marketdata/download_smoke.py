from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal, InvalidOperation
import sqlite3,time
from .sqlite_store import SQLiteMarketStore,Candle

@dataclass(frozen=True)
class DownloadSmokeResult:
    ok:bool; count:int; duplicates:int; gaps:int; detail:str=''

def validate_candle_smoke(rows,start_ms,end_ms,step=60_000):
    times=sorted(int(r[0]) for r in rows if start_ms<=int(r[0])<=end_ms)
    duplicates=len(times)-len(set(times))
    unique=sorted(set(times))
    gaps=sum(1 for a,b in zip(unique,unique[1:]) if b-a!=step)
    expected=((end_ms-start_ms)//step)+1 if end_ms>=start_ms else 0
    ok=bool(unique) and duplicates==0 and gaps==0 and len(unique)==expected
    return DownloadSmokeResult(ok,len(unique),duplicates,gaps,
        f'expected={expected} first={unique[0] if unique else None} last={unique[-1] if unique else None}')

def _checked_smoke_candles(rows, start_ms: int, end_ms: int):
    """Reject malformed injected OHLCV before opening disposable storage."""
    if not isinstance(rows, (list, tuple)):
        return None
    checked = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 7:
            return None
        try:
            raw_time = row[0]
            if type(raw_time) not in (str, int):
                return None
            timestamp = int(raw_time)
            if str(raw_time) != str(timestamp):
                return None
            if not start_ms <= timestamp <= end_ms or timestamp % 60_000:
                return None
            values = []
            for raw in row[1:7]:
                if type(raw) not in (str, int, float, Decimal):
                    return None
                value = Decimal(str(raw))
                if not value.is_finite():
                    return None
                converted = float(value)
                if not (-float("inf") < converted < float("inf")):
                    return None
                # SQLiteMarketStore.Candle stores binary64 values. Refuse
                # any nonzero source value that would silently underflow to 0.
                if value != 0 and converted == 0:
                    return None
                # Source -0 cannot be normalized into a trusted zero volume.
                if value.is_zero() and value.is_signed():
                    return None
                values.append(converted)
        except (ValueError, TypeError, InvalidOperation, OverflowError):
            return None
        o, h, l, c, volume, turnover = values
        if min(o, h, l, c) <= 0 or not (l <= o <= h and l <= c <= h):
            return None
        if volume < 0 or turnover < 0:
            return None
        checked.append(Candle('BTCUSDT', '1m', timestamp, o, h, l, c, volume, turnover, True))
    return checked


def run_download_smoke(root:Path,client=None,minutes=10,clock_ms=None):
    """Run a disposable local coverage smoke using an explicit managed reader.

    No implicit Bybit client or outbound exchange network is ever constructed.
    The legacy `root` parameter is retained for callers but is NEVER used for
    test artifacts: smoke DB/WAL are created only in a private OS tempdir.
    This is a coverage smoke, NOT proof of raw exchange source authenticity.
    The future Root integration must inject a source-admitted Grid reader.
    """
    if client is None or not callable(getattr(client,'fetch_klines',None)):
        return DownloadSmokeResult(False,0,0,0,'MANAGED_GRID_READER_REQUIRED')
    if type(minutes) is not int or not 1<=minutes<=1000:
        return DownloadSmokeResult(False,0,0,0,'INVALID_SMOKE_MINUTES')
    now=(clock_ms or (lambda:int(time.time()*1000)))()
    if type(now) is not int or now<=(minutes+2)*60_000:
        return DownloadSmokeResult(False,0,0,0,'INVALID_SMOKE_CLOCK')
    end=((now//60_000)-2)*60_000; start=end-(minutes-1)*60_000
    try:
        rows=client.fetch_klines('BTCUSDT',start,end,'1',limit=max(10,minutes))
    except Exception:
        return DownloadSmokeResult(False,0,0,0,'MANAGED_GRID_READER_ERROR')
    candles=_checked_smoke_candles(rows,start,end)
    if candles is None:
        return DownloadSmokeResult(False,0,0,0,'INVALID_MANAGED_GRID_ROWS')
    valid=validate_candle_smoke([(c.open_time,) for c in candles],start,end)
    if not valid.ok:return valid
    with TemporaryDirectory(prefix='strattester-grid-smoke-') as tmp:
        path=Path(tmp)/'market_download_smoke.sqlite3'
        store=None
        try:
            store=SQLiteMarketStore.open(path)
            stats=store.upsert_candles(candles)
            cov=store.coverage('BTCUSDT','candles','1m')
            store.close()
            store=None
            con=sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True)
            try: integrity=str(con.execute('PRAGMA quick_check').fetchone()[0]).lower()
            finally: con.close()
            ok=integrity=='ok' and cov.count==valid.count and not cov.gaps and stats.rejected==0
            return DownloadSmokeResult(ok,cov.count,valid.duplicates,len(cov.gaps),
                f'source=INJECTED_NOT_EXCHANGE_ATTESTED; sqlite={integrity}; {valid.detail}')
        finally:
            if store is not None:
                store.close()
