"""Optional read-only research gateway for Terminan, no migrations or writes."""
import json
import os
import re
import sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs

SYMBOL=re.compile(r'^[A-Z0-9]{2,30}$')

def runs(symbol,limit=100):
    if not SYMBOL.fullmatch(symbol):raise ValueError('invalid symbol')
    path=os.environ.get('TERMINAN_RESULTS_DB')
    if not path or not Path(path).is_file():return {'version':1,'symbol':symbol,'state':'SOURCE_UNAVAILABLE','runs':[]}
    con=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    try:
        rows=con.execute('SELECT run_id,strategy_id,strategy_version,created_at,metrics,job_id,lease_token,node_generation FROM research_results WHERE symbol=? ORDER BY created_at DESC LIMIT ?',(symbol,max(1,min(int(limit),500)))).fetchall()
        return {'version':1,'symbol':symbol,'state':'AVAILABLE','runs':[dict(run_id=r[0],strategy_id=r[1],strategy_version=r[2],created_at=r[3],metrics=json.loads(r[4]),fenced=bool(r[5] and r[6] and r[7])) for r in rows]}
    finally:con.close()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u=urlsplit(self.path);q=parse_qs(u.query)
        try:
            if u.path!='/v1/runs':raise ValueError('unknown endpoint')
            result=runs(q.get('symbol',['BTCUSDT'])[0],q.get('limit',[100])[0]);status=200
        except ValueError as e:result={'error':str(e)};status=400
        except Exception:result={'error':'source unavailable'};status=503
        body=json.dumps(result,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

def main():
    ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('TERMINAN_STRAT_PORT','18767'))),Handler).serve_forever()

if __name__=='__main__':main()
