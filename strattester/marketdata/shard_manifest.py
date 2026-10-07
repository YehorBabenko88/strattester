from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sqlite3,time

class ShardState(str,Enum):
    LEGACY='LEGACY'
    MIGRATING='MIGRATING'
    SHARD_READY='SHARD_READY'
    FAILED='FAILED'

@dataclass(frozen=True)
class ShardRecord:
    symbol:str
    state:ShardState
    updated_at:float
    rows_copied:int=0
    error:str|None=None

class ShardManifest:
    def __init__(self,path,con):
        self.path=Path(path); self.con=con
    @classmethod
    def open(cls,path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(path,timeout=30)
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA busy_timeout=30000')
        con.execute('PRAGMA synchronous=FULL')
        con.execute('''CREATE TABLE IF NOT EXISTS shard_manifest(
            symbol TEXT PRIMARY KEY,state TEXT NOT NULL,updated_at REAL NOT NULL,
            rows_copied INTEGER NOT NULL DEFAULT 0,error TEXT)''')
        con.commit(); return cls(path,con)
    def get(self,symbol):
        row=self.con.execute('SELECT symbol,state,updated_at,rows_copied,error FROM shard_manifest WHERE symbol=?',
                             (str(symbol).upper(),)).fetchone()
        return None if row is None else ShardRecord(row[0],ShardState(row[1]),row[2],row[3],row[4])
    def set(self,symbol,state,rows_copied=0,error=None,now=None):
        now=time.time() if now is None else float(now)
        with self.con:
            self.con.execute('''INSERT INTO shard_manifest(symbol,state,updated_at,rows_copied,error)
                VALUES(?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET
                state=excluded.state,updated_at=excluded.updated_at,
                rows_copied=excluded.rows_copied,error=excluded.error''',
                (str(symbol).upper(),ShardState(state).value,now,int(rows_copied),error))
        return self.get(symbol)
    def ready(self,symbol):
        r=self.get(symbol)
        return bool(r and r.state is ShardState.SHARD_READY)
    def pending(self,limit=None):
        sql="SELECT symbol,state,updated_at,rows_copied,error FROM shard_manifest WHERE state!='SHARD_READY' ORDER BY updated_at,symbol"
        if limit is not None: sql+=f' LIMIT {max(0,int(limit))}'
        return [ShardRecord(r[0],ShardState(r[1]),r[2],r[3],r[4]) for r in self.con.execute(sql)]
    def close(self): self.con.close()
