from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3,time
from .bybit_client import BybitClient
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
    client=client or BybitClient(); now=(clock_ms or (lambda:int(time.time()*1000)))()
    end=((now//60_000)-2)*60_000; start=end-(int(minutes)-1)*60_000
    rows=client.fetch_klines('BTCUSDT',start,end,'1',limit=max(10,int(minutes)))
    valid=validate_candle_smoke(rows,start,end)
    if not valid.ok:return valid
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    path=root/'market_download_smoke.sqlite3'
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
        return DownloadSmokeResult(ok,cov.count,valid.duplicates,len(cov.gaps),f'sqlite={integrity}; {valid.detail}')
    finally:
        if store is not None:
            store.close()
        for suffix in ('','-wal','-shm'):
            p=Path(str(path)+suffix)
            try:p.unlink()
            except FileNotFoundError:pass
