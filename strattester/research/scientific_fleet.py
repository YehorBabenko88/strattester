"""Operational health gate joining worker placement with the scientific Brain."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .adaptive_role_allocator import AdaptiveRoleAllocator,WorkerNode,RoleRequest,RolePlacement

@dataclass(frozen=True)
class ScientificFleetPlan:
    placements:dict[str,RolePlacement]
    execution_healthy:bool
    reasons:tuple[str,...]

class ScientificFleetCoordinator:
    def __init__(self,allocator:AdaptiveRoleAllocator|None=None):
        self.allocator=allocator or AdaptiveRoleAllocator()

    def plan(self,nodes:Iterable[WorkerNode],requests:Iterable[RoleRequest]):
        rs=tuple(requests);ps=self.allocator.allocate(rs,nodes)
        critical=[r.role for r in rs if r.critical]
        ok,reasons=self.allocator.execution_health(ps,critical)
        return ScientificFleetPlan(ps,ok,reasons)

    def permission(self,plan:ScientificFleetPlan,external_permission:bool):
        if not external_permission:return False,("external_permission_denied",)
        if not plan.execution_healthy:return False,tuple(f"fleet:{r}" for r in plan.reasons)
        return True,()
