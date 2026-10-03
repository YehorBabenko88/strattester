from __future__ import annotations
from pathlib import Path
import time,json,sqlite3,shutil
import psutil

class ControlStatus:
    def __init__(self,root:Path,clock=time.time,stale_after=60):
        self.root=Path(root); self.clock=clock; self.stale_after=stale_after
    def status(self):
        p=self.root/'state'/'worker-heartbeat'
        if not p.exists(): return {'worker':'DOWN','heartbeat_age_seconds':None}
        try: age=max(0,float(self.clock())-float(p.read_text(encoding='utf-8').strip()))
        except (OSError,ValueError): return {'worker':'DOWN','heartbeat_age_seconds':None}
        return {'worker':'UP' if age<=self.stale_after else 'DOWN','heartbeat_age_seconds':age}
    def jobs(self):
        db=self.root/'state'/'strattester_state.sqlite3'
        if not db.exists(): return {'total':0,'states':{}}
        con=sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True)
        try:
            states={}
            for (payload,) in con.execute('SELECT payload FROM jobs'):
                state=json.loads(payload).get('state','UNKNOWN')
                states[state]=states.get(state,0)+1
            return {'total':sum(states.values()),'states':states}
        finally: con.close()
    def results(self,symbol,strategy_id):
        p=self.root/'results'/'research_results.sqlite3'
        if not p.exists(): return None
        con=sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)
        try:
            row=con.execute('''SELECT run_id,symbol,strategy_id,strategy_version,created_at,metrics
                FROM research_results WHERE symbol=? AND strategy_id=? ORDER BY created_at DESC LIMIT 1''',
                (symbol.upper(),strategy_id)).fetchone()
        finally: con.close()
        if row is None:return None
        return {'run_id':row[0],'symbol':row[1],'strategy_id':row[2],'strategy_version':row[3],
                'created_at':row[4],'metrics':json.loads(row[5])}
    def resources(self):
        vm=psutil.virtual_memory(); disk=shutil.disk_usage(self.root)
        return {'ram_total':vm.total,'ram_available':vm.available,'ram_percent':vm.percent,
                'disk_free':disk.free,'disk_total':disk.total,'cpu_percent':psutil.cpu_percent(interval=None)}
    def database(self):
        p=self.root/'data'/'bybit_1m.sqlite3'
        if not p.exists(): return {'exists':False,'size_bytes':0,'integrity':'missing'}
        try:
            con=sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)
            try: integrity=str(con.execute('PRAGMA quick_check').fetchone()[0])
            finally: con.close()
        except sqlite3.Error as exc: integrity=str(exc)
        return {'exists':True,'size_bytes':p.stat().st_size,'integrity':integrity}
    def errors(self,lines=100):
        rows=[]
        for component in ('worker','controller'):
            for raw in self.tail_log(component,lines):
                try: item=json.loads(raw)
                except json.JSONDecodeError: continue
                if str(item.get('level','')).upper() in ('ERROR','CRITICAL'):
                    item.setdefault('component',component); rows.append(item)
        return rows[-max(1,min(int(lines),1000)):]
    def health(self):
        s=self.status(); db=self.database(); r=self.resources()
        return {'worker':s['worker'],'database_ok':db['integrity']=='ok',
                'disk_free':r['disk_free'],'ram_available':r['ram_available']}
    def tail_log(self,component='worker',lines=100):
        safe={'worker':'worker.jsonl','controller':'controller.jsonl'}
        if component not in safe: raise ValueError('component')
        p=self.root/'logs'/safe[component]
        if not p.exists(): return []
        with p.open('r',encoding='utf-8',errors='replace') as f:
            return f.read().splitlines()[-max(1,min(int(lines),1000)):]
