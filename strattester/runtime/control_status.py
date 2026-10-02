from __future__ import annotations
from pathlib import Path
import time,json,sqlite3

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
    def tail_log(self,component='worker',lines=100):
        safe={'worker':'worker.jsonl','controller':'controller.jsonl'}
        if component not in safe: raise ValueError('component')
        p=self.root/'logs'/safe[component]
        if not p.exists(): return []
        with p.open('r',encoding='utf-8',errors='replace') as f:
            return f.read().splitlines()[-max(1,min(int(lines),1000)):]
