"""Quorum and fencing for the distributed scientific Brain.

Only a majority-connected partition holding the current epoch/lease may authorize
execution. Minority or stale partitions remain research-capable but fail closed.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import floor
from typing import Iterable

@dataclass(frozen=True)
class BrainLease:
    holder:str
    epoch:int
    expires_ms:int

@dataclass(frozen=True)
class PartitionView:
    node_id:str
    visible_nodes:frozenset[str]
    epoch:int
    now_ms:int
    membership_generation:int=0

@dataclass(frozen=True)
class QuorumReport:
    node_id:str
    quorum_size:int
    visible:int
    majority:bool
    lease_valid:bool
    fenced:bool
    execution_allowed:bool
    reasons:tuple[str,...]
    membership_generation:int=0

class BrainQuorumFence:
    def __init__(self,members:Iterable[str],membership_generation:int=0):
        self.members=frozenset(map(str,members));self.membership_generation=int(membership_generation)
        if not self.members or any(not x for x in self.members):raise ValueError("members required")
        if self.membership_generation<0:raise ValueError("invalid membership generation")

    @property
    def quorum_size(self):
        return floor(len(self.members)/2)+1

    def assess(self,view:PartitionView,lease:BrainLease|None):
        visible=len(self.members & view.visible_nodes)
        majority=visible>=self.quorum_size
        reasons=[]
        if view.node_id not in self.members:reasons.append("unknown_member")
        generation_valid=view.membership_generation==self.membership_generation
        if not generation_valid:reasons.append("stale_membership_generation")
        if not majority:reasons.append("no_majority_quorum")
        lease_valid=bool(lease and lease.holder==view.node_id and
                         lease.epoch==view.epoch and view.now_ms<lease.expires_ms)
        if lease is None:reasons.append("missing_brain_lease")
        elif lease.epoch!=view.epoch:reasons.append("stale_epoch")
        elif lease.holder!=view.node_id:reasons.append("not_lease_holder")
        elif view.now_ms>=lease.expires_ms:reasons.append("lease_expired")
        fenced=not (majority and lease_valid and generation_valid and view.node_id in self.members)
        return QuorumReport(view.node_id,self.quorum_size,visible,majority,lease_valid,
                            fenced,not fenced,tuple(reasons),self.membership_generation)

    def can_renew(self,view:PartitionView,current:BrainLease|None):
        report=self.assess(view,current)
        return report.majority and not report.fenced and view.node_id in self.members and (
            current is None or current.holder==view.node_id or view.now_ms>=current.expires_ms)

    def next_epoch(self,current:BrainLease|None):
        return 1 if current is None else current.epoch+1
