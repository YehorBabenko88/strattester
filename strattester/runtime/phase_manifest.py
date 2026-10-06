"""Durable phase manifest shared with Bybit Cluster Grid."""
from __future__ import annotations
from pathlib import Path
import json,time

PHASES=("INFRASTRUCTURE","MARKET_HISTORY_SYNC","HISTORICAL_STRATEGY_RESEARCH",
        "HISTORICAL_SCIENCE_BOOTSTRAP","GRID_IMPORT","LIVE_LEARNING","PAPER_TRADING")

class PhaseManifest:
    def __init__(self,path):self.path=Path(path)
    def load(self):
        if not self.path.exists():return {"phase":"INFRASTRUCTURE","completed":[],"updated_at":time.time()}
        try:return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError,ValueError):return {"phase":"INFRASTRUCTURE","completed":[],"updated_at":time.time(),"corrupt":True}
    def advance(self,phase,details=None):
        if phase not in PHASES:raise ValueError("unknown phase")
        state=self.load();cur=PHASES.index(state.get("phase","INFRASTRUCTURE"));nxt=PHASES.index(phase)
        if nxt<cur:raise ValueError("phase regression is not allowed")
        completed=list(dict.fromkeys(list(state.get("completed") or [])+PHASES[cur:nxt]))
        out={"phase":phase,"completed":completed,"details":details or {},
             "updated_at":time.time(),"schema":1}
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        tmp.write_text(json.dumps(out,sort_keys=True,indent=2),encoding="utf-8")
        tmp.replace(self.path)
        return out
