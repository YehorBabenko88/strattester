from __future__ import annotations
from pathlib import Path
import time

class ControlStatus:
    def __init__(self,root:Path,clock=time.time,stale_after=60):
        self.root=Path(root); self.clock=clock; self.stale_after=stale_after
    def status(self):
        p=self.root/'state'/'worker-heartbeat'
        if not p.exists(): return {'worker':'DOWN','heartbeat_age_seconds':None}
        try: age=max(0,float(self.clock())-float(p.read_text(encoding='utf-8').strip()))
        except (OSError,ValueError): return {'worker':'DOWN','heartbeat_age_seconds':None}
        return {'worker':'UP' if age<=self.stale_after else 'DOWN','heartbeat_age_seconds':age}
    def tail_log(self,component='worker',lines=100):
        safe={'worker':'worker.jsonl','controller':'controller.jsonl'}
        if component not in safe: raise ValueError('component')
        p=self.root/'logs'/safe[component]
        if not p.exists(): return []
        with p.open('r',encoding='utf-8',errors='replace') as f:
            return f.read().splitlines()[-max(1,min(int(lines),1000)):]
