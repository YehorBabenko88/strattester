from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable
from .coverage import Coverage, TimeRange
from .schema import SCHEMA_SQL, SCHEMA_VERSION

@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float | None = None
    complete: bool = True

@dataclass(frozen=True)
class WriteStats:
    accepted: int = 0
    unchanged: int = 0
    rejected: int = 0

class SQLiteMarketStore:
    def __init__(self,path: Path,connection: sqlite3.Connection):
        self.path=Path(path); self.connection=connection

    @classmethod
    def open(cls,path: Path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(path)
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript(SCHEMA_SQL)
        con.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version',?)",(str(SCHEMA_VERSION),))
        con.commit()
        return cls(path,con)

    def close(self): self.connection.close()

    @staticmethod
    def _valid(c: Candle) -> bool:
        return bool(c.symbol and c.timeframe and c.open_time>=0 and c.low<=c.high and c.low<=c.open<=c.high and c.low<=c.close<=c.high and c.volume>=0)

    def upsert_candles(self,records: Iterable[Candle]) -> WriteStats:
        accepted=unchanged=rejected=0
        with self.connection:
            for c in records:
                if not self._valid(c):
                    rejected+=1; continue
                row=self.connection.execute(
                    'SELECT open,high,low,close,volume,turnover,complete FROM candles WHERE symbol=? AND timeframe=? AND open_time=?',
                    (c.symbol,c.timeframe,c.open_time)).fetchone()
                values=(c.open,c.high,c.low,c.close,c.volume,c.turnover,int(c.complete))
                if row is not None:
                    if tuple(row)==values:
                        unchanged+=1; continue
                    if bool(row[6]) and not c.complete:
                        rejected+=1; continue
                self.connection.execute(
                    '''INSERT INTO candles(symbol,timeframe,open_time,open,high,low,close,volume,turnover,complete)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(symbol,timeframe,open_time) DO UPDATE SET
                    open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
                    volume=excluded.volume,turnover=excluded.turnover,complete=excluded.complete''',
                    (c.symbol,c.timeframe,c.open_time,c.open,c.high,c.low,c.close,c.volume,c.turnover,int(c.complete)))
                accepted+=1
        return WriteStats(accepted,unchanged,rejected)

    def coverage(self,symbol:str,dataset:str='candles',timeframe:str='1m',step_ms:int=60_000)->Coverage:
        if dataset!='candles': raise ValueError('unsupported dataset')
        rows=self.connection.execute('SELECT open_time FROM candles WHERE symbol=? AND timeframe=? ORDER BY open_time',(symbol,timeframe)).fetchall()
        if not rows: return Coverage(None,None,0,())
        times=[r[0] for r in rows]; gaps=[]
        for a,b in zip(times,times[1:]):
            if b-a>step_ms: gaps.append(TimeRange(a+step_ms,b-step_ms))
        return Coverage(times[0],times[-1],len(times),tuple(gaps))

    def iter_candles(self,symbol:str,timeframe:str='1m',batch_size:int=20_000):
        cur=self.connection.execute('SELECT symbol,timeframe,open_time,open,high,low,close,volume,turnover,complete FROM candles WHERE symbol=? AND timeframe=? ORDER BY open_time',(symbol,timeframe))
        while True:
            batch=cur.fetchmany(batch_size)
            if not batch: break
            for r in batch: yield Candle(*r[:-1],complete=bool(r[-1]))
