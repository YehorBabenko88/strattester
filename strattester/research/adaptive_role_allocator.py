"""Adaptive assignment of scientific roles to distributed worker nodes.

Placement is sparse, capability-aware and redundancy-aware. Critical roles may
have independent backups, but clone concentration and unhealthy nodes are avoided.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable,Mapping
from math import isfinite

@dataclass(frozen=True)
class WorkerNode:
    node_id:str
    capabilities:frozenset[str]
    healthy:bool=True
    load:float=0.0
    latency_ms:float=0.0
    failure_rate:float=0.0
    domain:str="default"
    capacity_cost:float=0.15
    communication_quality:float=1.0

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
        if not all(isfinite(x) for x in (self.max_load,self.max_failure_rate,self.latency_scale_ms)) or not 0<self.max_load<=1 or not 0<=self.max_failure_rate<=1 or self.latency_scale_ms<=0:
            raise ValueError("invalid allocator thresholds")

    def _score(self,n:WorkerNode,load_override:float|None=None):
        vals=(n.load,n.latency_ms,n.failure_rate,n.capacity_cost,n.communication_quality)
        if not all(isfinite(float(x)) for x in vals) or not 0<=n.load<=1 or n.latency_ms<0 or not 0<=n.failure_rate<=1 or not 0<n.capacity_cost<=1 or not 0<=n.communication_quality<=1:
            return -1.0
        load=n.load if load_override is None else float(load_override)
        if not n.healthy or load>=self.max_load or n.failure_rate>self.max_failure_rate:return -1.0
        return (1-load)*(1-n.failure_rate)*n.communication_quality/(1+n.latency_ms/max(1,self.latency_scale_ms))

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
        ns=tuple(nodes);reserved={n.node_id:float(n.load) for n in ns};out={}
        for r in requests:
            projected=tuple(WorkerNode(n.node_id,n.capabilities,n.healthy,reserved[n.node_id],
                n.latency_ms,n.failure_rate,n.domain,n.capacity_cost,n.communication_quality) for n in ns)
            p=self.place(r,projected);out[r.role]=p
            by_id={n.node_id:n for n in ns}
            for node_id in p.nodes:
                n=by_id[node_id];reserved[node_id]=min(1.0,reserved[node_id]+n.capacity_cost)
        return out

    def execution_health(self,placements:Mapping[str,RolePlacement],critical_roles:Iterable[str]):
        reasons=[]
        for role in critical_roles:
            p=placements.get(role)
            if p is None:reasons.append(f"missing_role:{role}")
            elif p.degraded:reasons.extend(f"{role}:{x}" for x in p.reasons)
        return not reasons,tuple(reasons)
