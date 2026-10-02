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
        cols={r[1] for r in connection.execute('PRAGMA table_info(candles)')}
        self._legacy_candles='ts' in cols and 'open_time' not in cols

    @classmethod
    def open(cls,path: Path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(path)
        con.execute('PRAGMA foreign_keys=ON')
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        legacy=False
        if 'candles' in tables:
            cols={r[1] for r in con.execute('PRAGMA table_info(candles)')}
            legacy='ts' in cols and 'open_time' not in cols
        if legacy:
            for statement in SCHEMA_SQL.split(';'):
                stmt=statement.strip()
                if not stmt or 'CREATE TABLE IF NOT EXISTS candles' in stmt or 'idx_candles_lookup' in stmt:
                    continue
                con.execute(stmt)
        else:
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
                if self._legacy_candles:
                    if c.timeframe!='1m' or not c.complete:
                        rejected+=1; continue
                    row=self.connection.execute(
                        'SELECT open,high,low,close,volume,turnover FROM candles WHERE symbol=? AND ts=?',
                        (c.symbol,c.open_time)).fetchone()
                    values=(c.open,c.high,c.low,c.close,c.volume,c.turnover)
                    if row is not None and tuple(row)==values:
                        unchanged+=1; continue
                    self.connection.execute(
                        '''INSERT INTO candles(symbol,ts,open,high,low,close,volume,turnover)
                        VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(symbol,ts) DO UPDATE SET
                        open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
                        volume=excluded.volume,turnover=excluded.turnover''',
                        (c.symbol,c.open_time,c.open,c.high,c.low,c.close,c.volume,c.turnover))
                    accepted+=1; continue
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


    @staticmethod
    def _write_scalar_rows(connection,table,key_columns,value_columns,rows):
        accepted=unchanged=rejected=0
        for keys,values in rows:
            where=' AND '.join(f'{k}=?' for k in key_columns)
            existing=connection.execute(f"SELECT {','.join(value_columns)} FROM {table} WHERE {where}",tuple(keys)).fetchone()
            values=tuple(values)
            if existing is not None and tuple(existing)==values:
                unchanged+=1; continue
            cols=tuple(key_columns)+tuple(value_columns)
            placeholders=','.join('?' for _ in cols)
            updates=','.join(f'{x}=excluded.{x}' for x in value_columns)
            connection.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({placeholders}) ON CONFLICT({','.join(key_columns)}) DO UPDATE SET {updates}",tuple(keys)+values)
            accepted+=1
        return WriteStats(accepted,unchanged,rejected)

    def upsert_price_klines(self,dataset:str,symbol:str,rows,timeframe:str='1m')->WriteStats:
        tables={'mark_price':'mark_prices','index_price':'index_prices','premium_index':'premium_index'}
        if dataset not in tables: raise ValueError('unsupported price dataset')
        parsed=[]; rejected=0
        for r in rows:
            try:
                ts=int(r[0]); o,h,l,cl=map(float,r[1:5])
                if min(o,h,l,cl)<=0 or l>h or not (l<=o<=h and l<=cl<=h): raise ValueError
                parsed.append(((symbol,timeframe,ts),(o,h,l,cl,1)))
            except (TypeError,ValueError,IndexError):
                rejected+=1
        with self.connection:
            s=self._write_scalar_rows(self.connection,tables[dataset],('symbol','timeframe','open_time'),('open','high','low','close','complete'),parsed)
        return WriteStats(s.accepted,s.unchanged,s.rejected+rejected)

    def upsert_open_interest(self,symbol:str,rows,timeframe:str='5m')->WriteStats:
        parsed=[]; rejected=0
        for r in rows:
            try:
                ts=int(r.get('timestamp') or r.get('time')); value=float(r.get('openInterest'))
                if ts<0 or value<0: raise ValueError
                parsed.append(((symbol,timeframe,ts),(value,1)))
            except (AttributeError,TypeError,ValueError):
                rejected+=1
        with self.connection:
            s=self._write_scalar_rows(self.connection,'open_interest',('symbol','timeframe','open_time'),('value','complete'),parsed)
        return WriteStats(s.accepted,s.unchanged,s.rejected+rejected)

    def upsert_funding(self,symbol:str,rows)->WriteStats:
        parsed=[]; rejected=0
        for r in rows:
            try:
                ts=int(r.get('fundingRateTimestamp')); value=float(r.get('fundingRate'))
                if ts<0: raise ValueError
                parsed.append(((symbol,ts),(value,)))
            except (AttributeError,TypeError,ValueError):
                rejected+=1
        with self.connection:
            s=self._write_scalar_rows(self.connection,'funding',('symbol','funding_time'),('rate',),parsed)
        return WriteStats(s.accepted,s.unchanged,s.rejected+rejected)

    def upsert_long_short_ratio(self,symbol:str,rows,timeframe:str='5m')->WriteStats:
        parsed=[]; rejected=0
        for r in rows:
            try:
                ts=int(r.get('timestamp')); buy=float(r.get('buyRatio')); sell=float(r.get('sellRatio'))
                ratio=buy/sell if sell else None
                if ts<0 or buy<0 or sell<0: raise ValueError
                parsed.append(((symbol,timeframe,ts),(buy,sell,ratio)))
            except (AttributeError,TypeError,ValueError):
                rejected+=1
        with self.connection:
            s=self._write_scalar_rows(self.connection,'long_short_ratio',('symbol','timeframe','open_time'),('buy_ratio','sell_ratio','long_short_ratio'),parsed)
        return WriteStats(s.accepted,s.unchanged,s.rejected+rejected)

    def coverage(self,symbol:str,dataset:str='candles',timeframe:str='1m',step_ms:int=60_000)->Coverage:
        mapping={
            'candles':('candles','open_time',True),
            'mark_price':('mark_prices','open_time',True),
            'index_price':('index_prices','open_time',True),
            'premium_index':('premium_index','open_time',True),
            'open_interest':('open_interest','open_time',True),
            'funding':('funding','funding_time',False),
            'long_short_ratio':('long_short_ratio','open_time',True),
            'public_trades':('public_trade_aggregates','open_time',True),
        }
        if dataset not in mapping: raise ValueError('unsupported dataset')
        if dataset=='candles' and self._legacy_candles:
            if timeframe!='1m': return Coverage(None,None,0,())
            rows=self.connection.execute('SELECT ts FROM candles WHERE symbol=? ORDER BY ts',(symbol,)).fetchall()
            if not rows:return Coverage(None,None,0,())
            times=[r[0] for r in rows]; gaps=[]
            for a,b in zip(times,times[1:]):
                if b-a>step_ms:gaps.append(TimeRange(a+step_ms,b-step_ms))
            return Coverage(times[0],times[-1],len(times),tuple(gaps))
        table,time_col,uses_tf=mapping[dataset]
        if uses_tf:
            rows=self.connection.execute(f'SELECT {time_col} FROM {table} WHERE symbol=? AND timeframe=? ORDER BY {time_col}',(symbol,timeframe)).fetchall()
        else:
            rows=self.connection.execute(f'SELECT {time_col} FROM {table} WHERE symbol=? ORDER BY {time_col}',(symbol,)).fetchall()
        if not rows:return Coverage(None,None,0,())
        times=[r[0] for r in rows]; gaps=[]
        for a,b in zip(times,times[1:]):
            if b-a>step_ms:gaps.append(TimeRange(a+step_ms,b-step_ms))
        return Coverage(times[0],times[-1],len(times),tuple(gaps))

    def iter_candles(self,symbol:str,timeframe:str='1m',batch_size:int=20_000):
        if self._legacy_candles:
            if timeframe!='1m': return
            cur=self.connection.execute('SELECT symbol,ts,open,high,low,close,volume,turnover FROM candles WHERE symbol=? ORDER BY ts',(symbol,))
            while True:
                batch=cur.fetchmany(batch_size)
                if not batch: break
                for r in batch:
                    yield Candle(r[0],'1m',r[1],r[2],r[3],r[4],r[5],r[6],r[7],True)
            return
        cur=self.connection.execute('SELECT symbol,timeframe,open_time,open,high,low,close,volume,turnover,complete FROM candles WHERE symbol=? AND timeframe=? ORDER BY open_time',(symbol,timeframe))
        while True:
            batch=cur.fetchmany(batch_size)
            if not batch: break
            for r in batch: yield Candle(*r[:-1],complete=bool(r[-1]))
