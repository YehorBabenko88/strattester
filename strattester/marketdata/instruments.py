from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import sqlite3
from pathlib import Path

class InstrumentStatus(str,Enum):
    PRE_LISTING='PRE_LISTING'; ACTIVE='ACTIVE'; SUSPENDED='SUSPENDED'; DELISTED='DELISTED'

@dataclass(frozen=True)
class InstrumentRecord:
    symbol:str; status:InstrumentStatus; first_seen:int; last_seen:int; delisted_at:int|None=None

class InstrumentRegistry:
    def __init__(self,conn): self.conn=conn
    @classmethod
    def open(cls,path:Path):
        c=sqlite3.connect(path)
        c.execute("CREATE TABLE IF NOT EXISTS instruments(symbol TEXT PRIMARY KEY,status TEXT NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,delisted_at INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS instrument_intervals(symbol TEXT NOT NULL,start_time INTEGER NOT NULL,end_time INTEGER,PRIMARY KEY(symbol,start_time))")
        c.commit(); return cls(c)
    def close(self): self.conn.close()
    def get(self,symbol):
        row=self.conn.execute("SELECT symbol,status,first_seen,last_seen,delisted_at FROM instruments WHERE symbol=?",(symbol,)).fetchone()
        return None if row is None else InstrumentRecord(row[0],InstrumentStatus(row[1]),row[2],row[3],row[4])
    def intervals(self,symbol):
        return self.conn.execute("SELECT start_time,end_time FROM instrument_intervals WHERE symbol=? ORDER BY start_time",(symbol,)).fetchall()
    def eligible_at(self,symbol,timestamp):
        return self.conn.execute("SELECT 1 FROM instrument_intervals WHERE symbol=? AND start_time<=? AND (end_time IS NULL OR ?<end_time) LIMIT 1",(symbol,timestamp,timestamp)).fetchone() is not None
    def set_status(self,symbol,status,observed_at):
        rec=self.get(symbol)
        if rec is None: raise KeyError(symbol)
        if rec.status is InstrumentStatus.ACTIVE and status is not InstrumentStatus.ACTIVE:
            self.conn.execute("UPDATE instrument_intervals SET end_time=? WHERE symbol=? AND end_time IS NULL",(observed_at,symbol))
        if rec.status is not InstrumentStatus.ACTIVE and status is InstrumentStatus.ACTIVE:
            self.conn.execute("INSERT OR IGNORE INTO instrument_intervals(symbol,start_time,end_time) VALUES(?,?,NULL)",(symbol,observed_at))
        delisted=observed_at if status is InstrumentStatus.DELISTED else (None if status is InstrumentStatus.ACTIVE else rec.delisted_at)
        self.conn.execute("UPDATE instruments SET status=?,last_seen=?,delisted_at=? WHERE symbol=?",(status.value,observed_at,delisted,symbol)); self.conn.commit()
    def reconcile(self,exchange_snapshot:set[str],observed_at:int):
        known={r[0]:InstrumentStatus(r[1]) for r in self.conn.execute("SELECT symbol,status FROM instruments")}
        for symbol in sorted(exchange_snapshot):
            if symbol not in known:
                self.conn.execute("INSERT INTO instruments VALUES(?,?,?,?,NULL)",(symbol,InstrumentStatus.ACTIVE.value,observed_at,observed_at))
                self.conn.execute("INSERT INTO instrument_intervals VALUES(?,?,NULL)",(symbol,observed_at))
            elif known[symbol] is not InstrumentStatus.ACTIVE:
                self.set_status(symbol,InstrumentStatus.ACTIVE,observed_at)
            else:
                self.conn.execute("UPDATE instruments SET last_seen=? WHERE symbol=?",(observed_at,symbol))
        for symbol,status in known.items():
            if status is InstrumentStatus.ACTIVE and symbol not in exchange_snapshot:
                self.set_status(symbol,InstrumentStatus.DELISTED,observed_at)
        self.conn.commit()
