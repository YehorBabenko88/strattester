from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json,time

class CommissioningStage(str,Enum):
    INFRASTRUCTURE='INFRASTRUCTURE'
    NODE_CONNECTIVITY='NODE_CONNECTIVITY'
    CONTROL_PLANE='CONTROL_PLANE'
    DATABASE='DATABASE'
    STORAGE='STORAGE'
    DATA_TRANSFER='DATA_TRANSFER'
    TELEGRAM='TELEGRAM'
    MINI_DATA='MINI_DATA'
    MINI_BACKTEST='MINI_BACKTEST'
    FAILURE_RECOVERY='FAILURE_RECOVERY'
    CLEAN_RESET='CLEAN_RESET'
    PRODUCTION_READY='PRODUCTION_READY'

ORDER=tuple(CommissioningStage)

@dataclass(frozen=True)
class StageResult:
    stage:CommissioningStage
    ok:bool
    detail:str
    checked_at:float

class CommissioningManifest:
    """Durable, fail-closed record of physical cluster commissioning."""
    def __init__(self,path:Path):
        self.path=Path(path)

    def load(self):
        if not self.path.exists():
            return {'schema':1,'mode':'COMMISSIONING','completed':[],'history':[]}
        return json.loads(self.path.read_text(encoding='utf-8'))

    def record(self,stage:CommissioningStage,ok:bool,detail:str,now=None):
        data=self.load(); completed=list(data.get('completed') or [])
        index=ORDER.index(stage)
        missing=[s.value for s in ORDER[:index] if s.value not in completed]
        if missing:
            raise RuntimeError(f'commissioning stage blocked; prerequisites missing: {missing}')
        event={'stage':stage.value,'ok':bool(ok),'detail':str(detail),
               'checked_at':time.time() if now is None else float(now)}
        data.setdefault('history',[]).append(event)
        if ok and stage.value not in completed: completed.append(stage.value)
        if not ok and stage.value in completed: completed.remove(stage.value)
        data['completed']=completed
        data['mode']='PRODUCTION_READY' if stage is CommissioningStage.PRODUCTION_READY and ok else 'COMMISSIONING'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(self.path.suffix+'.tmp')
        tmp.write_text(json.dumps(data,sort_keys=True,indent=2),encoding='utf-8')
        tmp.replace(self.path)
        return StageResult(stage,bool(ok),str(detail),event['checked_at'])

    def next_stage(self):
        completed=set(self.load().get('completed') or [])
        return next((s for s in ORDER if s.value not in completed),None)
