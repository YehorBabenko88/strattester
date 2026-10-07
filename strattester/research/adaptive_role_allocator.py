"""Adaptive assignment of scientific roles to distributed worker nodes.

Placement is sparse, capability-aware and redundancy-aware. Critical roles may
have independent backups, but clone concentration and unhealthy nodes are avoided.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable,Mapping

@dataclass(frozen=True)
class WorkerNode:
    node_id:str
    capabilities:frozenset[str]
    healthy:bool=True
    load:float=0.0
    latency_ms:float=0.0
    failure_rate:float=0.0
    domain:str="default"

@dataclass(frozen=True)
class RoleRequest:
    role:str
    capability:str
    critical:bool=False
    replicas:int=1

@dataclass(frozen=True)
class RolePlacement:
    role:str
    nodes:tuple[str,...]
    score:float
    degraded:bool
    reasons:tuple[str,...]

class AdaptiveRoleAllocator:
    def __init__(self,*,max_load=.9,max_failure_rate=.25,latency_scale_ms=500):
        self.max_load=float(max_load);self.max_failure_rate=float(max_failure_rate)
        self.latency_scale_ms=float(latency_scale_ms)

    def _score(self,n:WorkerNode):
        if not n.healthy or n.load>=self.max_load or n.failure_rate>self.max_failure_rate:return -1.0
        return (1-n.load)*(1-n.failure_rate)/(1+n.latency_ms/max(1,self.latency_scale_ms))

    def place(self,request:RoleRequest,nodes:Iterable[WorkerNode]):
        eligible=[n for n in nodes if request.capability in n.capabilities and self._score(n)>=0]
        eligible.sort(key=lambda n:(-self._score(n),n.node_id))
        wanted=max(1,request.replicas,2 if request.critical else 1)
        chosen=[];domains=set()
        # First pass favors independent failure domains.
        for n in eligible:
            if n.domain in domains:continue
            chosen.append(n);domains.add(n.domain)
            if len(chosen)>=wanted:break
        for n in eligible:
            if len(chosen)>=wanted:break
            if n not in chosen:chosen.append(n)
        reasons=[]
        if not chosen:reasons.append("no_healthy_capable_node")
        if len(chosen)<wanted:reasons.append("insufficient_redundancy")
        if request.critical and len({n.domain for n in chosen})<min(2,wanted):
            reasons.append("shared_failure_domain")
        degraded=bool(reasons)
        score=min((self._score(n) for n in chosen),default=0.0)
        return RolePlacement(request.role,tuple(n.node_id for n in chosen),score,degraded,tuple(reasons))

    def allocate(self,requests:Iterable[RoleRequest],nodes:Iterable[WorkerNode]):
        ns=tuple(nodes)
        return {r.role:self.place(r,ns) for r in requests}

    def execution_health(self,placements:Mapping[str,RolePlacement],critical_roles:Iterable[str]):
        reasons=[]
        for role in critical_roles:
            p=placements.get(role)
            if p is None:reasons.append(f"missing_role:{role}")
            elif p.degraded:reasons.extend(f"{role}:{x}" for x in p.reasons)
        return not reasons,tuple(reasons)
