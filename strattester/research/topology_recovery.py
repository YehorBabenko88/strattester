"""Automatic recovery state machine for the distributed scientific brain."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable
from math import isfinite
from .adaptive_role_allocator import WorkerNode,RoleRequest
from .scientific_fleet import ScientificFleetCoordinator,ScientificFleetPlan

class RecoveryState(str,Enum):
    HEALTHY="HEALTHY"
    DEGRADED="DEGRADED"
    RECOVERING="RECOVERING"

@dataclass(frozen=True)
class RecoveryReport:
    state:RecoveryState
    plan:ScientificFleetPlan
    lost_nodes:tuple[str,...]
    recovered_nodes:tuple[str,...]
    uncertainty_addon:float
    execution_allowed:bool
    stable_cycles:int
    reasons:tuple[str,...]

class ScientificTopologyRecovery:
    def __init__(self,coordinator:ScientificFleetCoordinator|None=None,*,
                 stale_after_ms=15000,stabilization_cycles=3,max_uncertainty_addon=.5):
        self.coordinator=coordinator or ScientificFleetCoordinator()
        self.stale_after_ms=int(stale_after_ms);self.stabilization_cycles=int(stabilization_cycles)
        self.max_uncertainty_addon=float(max_uncertainty_addon)
        if self.stale_after_ms<=0 or self.stabilization_cycles<1 or not isfinite(self.max_uncertainty_addon) or not 0<=self.max_uncertainty_addon<=1:
            raise ValueError("invalid recovery parameters")
        self._last_seen={};self._known=set();self._state=RecoveryState.DEGRADED;self._stable=0
        self._previous_live=set()

    def heartbeat(self,node_id:str,timestamp_ms:int):
        node_id=str(node_id);ts=int(timestamp_ms)
        if not node_id:raise ValueError("node_id required")
        prior=self._last_seen.get(node_id)
        if prior is not None and ts<prior:return False
        self._last_seen[node_id]=ts;self._known.add(node_id);return True

    def _live(self,nodes:Iterable[WorkerNode],now_ms:int):
        live=[];lost=[]
        for n in nodes:
            seen=self._last_seen.get(n.node_id)
            if seen is None or now_ms-seen>self.stale_after_ms or not n.healthy:lost.append(n.node_id)
            else:live.append(n)
        return live,sorted(lost)

    def reconcile(self,nodes:Iterable[WorkerNode],requests:Iterable[RoleRequest],*,now_ms:int):
        nodes=tuple(nodes);live,lost=self._live(nodes,now_ms)
        plan=self.coordinator.plan(live,requests)
        live_ids={n.node_id for n in live}
        recovered=sorted(live_ids-self._previous_live if self._previous_live else set())
        reasons=list(plan.reasons)
        if lost:reasons.append("worker_loss:"+",".join(lost))
        if not plan.execution_healthy:
            self._state=RecoveryState.DEGRADED;self._stable=0
        else:
            if self._state==RecoveryState.HEALTHY and not lost:
                self._stable=max(self._stable,self.stabilization_cycles)
            else:
                self._state=RecoveryState.RECOVERING;self._stable+=1
                if self._stable>=self.stabilization_cycles:
                    self._state=RecoveryState.HEALTHY
        if self._state==RecoveryState.RECOVERING:reasons.append("topology_stabilizing")
        if self._state==RecoveryState.DEGRADED:reasons.append("topology_degraded")
        severity=1.0 if self._state==RecoveryState.DEGRADED else (.5 if self._state==RecoveryState.RECOVERING else 0)
        if lost:severity=max(severity,min(1.0,len(lost)/max(1,len(nodes))))
        uncertainty=self.max_uncertainty_addon*severity
        allowed=self._state==RecoveryState.HEALTHY and plan.execution_healthy
        self._previous_live=live_ids
        return RecoveryReport(self._state,plan,tuple(lost),tuple(recovered),uncertainty,
                              allowed,self._stable,tuple(dict.fromkeys(reasons)))
