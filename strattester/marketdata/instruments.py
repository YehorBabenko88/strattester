from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import sqlite3,hashlib,json
from pathlib import Path

class InstrumentStatus(str,Enum):
    PRE_LISTING='PRE_LISTING'; ACTIVE='ACTIVE'; SUSPENDED='SUSPENDED'; MISSING='MISSING'; DELISTED='DELISTED'

@dataclass(frozen=True)
class InstrumentRecord:
    symbol:str; status:InstrumentStatus; first_seen:int; last_seen:int; delisted_at:int|None=None

class InstrumentRegistry:
    def __init__(self,conn,missing_confirmations:int=2): self.conn=conn;self.missing_confirmations=max(1,int(missing_confirmations))
    @classmethod
    def open(cls,path:Path):
        c=sqlite3.connect(path)
        c.execute("CREATE TABLE IF NOT EXISTS instruments(symbol TEXT PRIMARY KEY,status TEXT NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,delisted_at INTEGER,missing_count INTEGER NOT NULL DEFAULT 0)")
        cols={r[1] for r in c.execute("PRAGMA table_info(instruments)")}
        if "missing_count" not in cols:c.execute("ALTER TABLE instruments ADD COLUMN missing_count INTEGER NOT NULL DEFAULT 0")
        c.execute("CREATE TABLE IF NOT EXISTS instrument_intervals(symbol TEXT NOT NULL,start_time INTEGER NOT NULL,end_time INTEGER,PRIMARY KEY(symbol,start_time))")
        c.execute("CREATE TABLE IF NOT EXISTS instrument_registry_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        c.commit(); return cls(c)
    def close(self): self.conn.close()
    def get(self,symbol):
        row=self.conn.execute("SELECT symbol,status,first_seen,last_seen,delisted_at FROM instruments WHERE symbol=?",(symbol,)).fetchone()
        return None if row is None else InstrumentRecord(row[0],InstrumentStatus(row[1]),row[2],row[3],row[4])
    def active_symbols(self):
        return {r[0] for r in self.conn.execute("SELECT symbol FROM instruments WHERE status=?",(InstrumentStatus.ACTIVE.value,))}
    def intervals(self,symbol):
        return self.conn.execute("SELECT start_time,end_time FROM instrument_intervals WHERE symbol=? ORDER BY start_time",(symbol,)).fetchall()
    def eligible_at(self,symbol,timestamp):
        return self.conn.execute("SELECT 1 FROM instrument_intervals WHERE symbol=? AND start_time<=? AND (end_time IS NULL OR ?<end_time) LIMIT 1",(symbol,timestamp,timestamp)).fetchone() is not None
    def _set_status(self,symbol,status,observed_at,commit=True):
        rec=self.get(symbol)
        if rec is None: raise KeyError(symbol)
        if rec.status is InstrumentStatus.ACTIVE and status is not InstrumentStatus.ACTIVE:
            self.conn.execute("UPDATE instrument_intervals SET end_time=? WHERE symbol=? AND end_time IS NULL",(observed_at,symbol))
        if rec.status is not InstrumentStatus.ACTIVE and status is InstrumentStatus.ACTIVE:
            self.conn.execute("INSERT OR IGNORE INTO instrument_intervals(symbol,start_time,end_time) VALUES(?,?,NULL)",(symbol,observed_at))
        delisted=observed_at if status is InstrumentStatus.DELISTED else (None if status is InstrumentStatus.ACTIVE else rec.delisted_at)
        missing_count=0 if status is InstrumentStatus.ACTIVE else self.conn.execute("SELECT missing_count FROM instruments WHERE symbol=?",(symbol,)).fetchone()[0]
        self.conn.execute("UPDATE instruments SET status=?,last_seen=?,delisted_at=?,missing_count=? WHERE symbol=?",(status.value,observed_at,delisted,int(missing_count or 0),symbol))
        if commit:self.conn.commit()
    def set_status(self,symbol,status,observed_at):
        return self._set_status(symbol,status,observed_at,commit=True)
    def reconcile(self,exchange_snapshot:set[str],observed_at:int):
        observed_at=int(observed_at)
        raw=list(exchange_snapshot)
        if any(not isinstance(x,str) or not x.strip() for x in raw):
            raise ValueError("instrument symbols must be non-empty strings")
        symbols={x.strip() for x in raw}
        digest=hashlib.sha256(json.dumps(sorted(symbols),separators=(',',':')).encode()).hexdigest()
        meta=dict(self.conn.execute("SELECT key,value FROM instrument_registry_meta"))
        previous_at=int(meta["last_reconcile_at"]) if "last_reconcile_at" in meta else None
        previous_hash=meta.get("last_snapshot_hash")
        if previous_at is not None:
            if observed_at<previous_at:raise ValueError("non-monotonic universe observation")
            if observed_at==previous_at:
                if digest==previous_hash:return
                raise ValueError("conflicting universe snapshot at identical timestamp")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            known={r[0]:InstrumentStatus(r[1]) for r in self.conn.execute("SELECT symbol,status FROM instruments")}
            for symbol in sorted(symbols):
                if symbol not in known:
                    self.conn.execute("INSERT INTO instruments(symbol,status,first_seen,last_seen,delisted_at,missing_count) VALUES(?,?,?,?,NULL,0)",(symbol,InstrumentStatus.ACTIVE.value,observed_at,observed_at))
                    self.conn.execute("INSERT INTO instrument_intervals VALUES(?,?,NULL)",(symbol,observed_at))
                elif known[symbol] is not InstrumentStatus.ACTIVE:
                    self._set_status(symbol,InstrumentStatus.ACTIVE,observed_at,commit=False)
                else:
                    self.conn.execute("UPDATE instruments SET last_seen=?,missing_count=0 WHERE symbol=?",(observed_at,symbol))
            for symbol,status in known.items():
                if symbol in symbols:continue
                if status in (InstrumentStatus.ACTIVE,InstrumentStatus.MISSING):
                    count=int(self.conn.execute("SELECT missing_count FROM instruments WHERE symbol=?",(symbol,)).fetchone()[0] or 0)+1
                    if count>=self.missing_confirmations:
                        self.conn.execute("UPDATE instruments SET missing_count=? WHERE symbol=?",(count,symbol))
                        self._set_status(symbol,InstrumentStatus.DELISTED,observed_at,commit=False)
                    else:
                        if status is InstrumentStatus.ACTIVE:self.conn.execute("UPDATE instrument_intervals SET end_time=? WHERE symbol=? AND end_time IS NULL",(observed_at,symbol))
                        self.conn.execute("UPDATE instruments SET status=?,missing_count=? WHERE symbol=?",(InstrumentStatus.MISSING.value,count,symbol))
            self.conn.execute("INSERT OR REPLACE INTO instrument_registry_meta(key,value) VALUES('last_reconcile_at',?)",(str(observed_at),))
            self.conn.execute("INSERT OR REPLACE INTO instrument_registry_meta(key,value) VALUES('last_snapshot_hash',?)",(digest,))
            self.conn.commit()
        except Exception:
            self.conn.rollback();raise
