from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
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
    rows=client.fetch_klines('BTCUSDT',start,end,'1',limit=max(10,minutes))
    valid=validate_candle_smoke(rows,start,end)
    if not valid.ok:return valid
    with TemporaryDirectory(prefix='strattester-grid-smoke-') as tmp:
        path=Path(tmp)/'market_download_smoke.sqlite3'
        store=None
        try:
            store=SQLiteMarketStore.open(path)
            candles=[Candle('BTCUSDT','1m',int(r[0]),float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[5]),float(r[6]),True) for r in rows if start<=int(r[0])<=end]
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
