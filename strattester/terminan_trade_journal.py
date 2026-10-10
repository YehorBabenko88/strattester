"""Optional append-only trade export for historical visualizations.

Source-owned journal: Strattester writes it, Terminan only reads it.
Not a market database and not an execution engine.
"""
import json
import sqlite3
from dataclasses import asdict,is_dataclass
from pathlib import Path

SCHEMA='''CREATE TABLE IF NOT EXISTS terminan_trade_events (
 run_id TEXT NOT NULL, symbol TEXT NOT NULL, strategy_id TEXT NOT NULL,
 trade_id TEXT NOT NULL, entry_ms INTEGER NOT NULL, exit_ms INTEGER,
 entry_price REAL NOT NULL, exit_price REAL, side TEXT NOT NULL,
 quantity REAL NOT NULL, gross_pnl REAL, fees REAL, net_pnl REAL,
 exit_reason TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(run_id,symbol,strategy_id,trade_id))'''

def init_journal(con):
    con.execute(SCHEMA)

def append_trades(con,run_id,symbol,strategy_id,trades):
    """Call only after an authoritative simulation run has completed."""
    with con:
        init_journal(con)
        for i,t in enumerate(trades):
            if is_dataclass(t):t=asdict(t)
            entry=int(t['entry_time']);exit_at=int(t['exit_time'])
            if exit_at<entry:raise ValueError('exit before entry')
            if t['side'] not in ('long','short'):raise ValueError('side')
            price=float(t['entry_price']);exit_price=float(t['exit_price'])
            if price<=0 or exit_price<=0:raise ValueError('price')
            # ResearchTrade is sized in quote currency; quantity cannot be inferred
            # without execution policy. Require source to supply it explicitly.
            qty=t.get('quantity')
            if qty is None:raise ValueError('quantity required for faithful visualization')
            if float(qty)<=0:raise ValueError('quantity')
            con.execute('''INSERT OR IGNORE INTO terminan_trade_events
             (run_id,symbol,strategy_id,trade_id,entry_ms,exit_ms,entry_price,exit_price,side,quantity,gross_pnl,fees,net_pnl,exit_reason,metadata_json)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
             (run_id,symbol,strategy_id,str(t.get('trade_id',i)),entry,exit_at,price,exit_price,t['side'],float(qty),t.get('gross_pnl'),t.get('fees'),t.get('net_pnl'),t.get('exit_reason'),json.dumps(t.get('metadata',{}),sort_keys=True)))

def read_trades(db_path,run_id,symbol,limit=500,after_trade_id=''):
    p=Path(db_path)
    if not p.is_file():return []
    con=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    try:
        cols='run_id,symbol,strategy_id,trade_id,entry_ms,exit_ms,entry_price,exit_price,side,quantity,gross_pnl,fees,net_pnl,exit_reason'
        rows=con.execute('SELECT '+cols+' FROM terminan_trade_events WHERE run_id=? AND symbol=? AND trade_id>? ORDER BY trade_id LIMIT ?', (run_id,symbol,after_trade_id,max(1,min(int(limit),500)))).fetchall()
        return [dict(zip(cols.split(','),r)) for r in rows]
    finally:con.close()
