"""Offline consolidation and forgetting for the scientific organism.

Maintenance is deliberately separated from online decision making. It can prune
weak stale channel influence, surface contradictions and propose a new native
snapshot, but cannot silently validate its own proposal.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Iterable
from .neuro_controller import NeuroDecisionController
from .homeostasis import HomeostaticSupervisor,ChannelLifecycle
from .credit_assignment import CreditAssigner
from .timescale_memory import MultiTimescaleMemory
from .stability_landscape import BrainStabilityLandscape

@dataclass(frozen=True)
class ConsolidationReport:
    pruned:tuple[str,...]
    protected:tuple[str,...]
    contradictions:tuple[str,...]
    native_updated:bool
    reasons:tuple[str,...]

class OfflineConsolidator:
    def __init__(self,*,stale_cycles=6,weak_conductance=.45,prune_step=.05,
                 min_native_validation=.75,min_native_families=2):
        self.stale_cycles=int(stale_cycles);self.weak_conductance=float(weak_conductance)
        self.prune_step=float(prune_step);self.min_native_validation=float(min_native_validation)
        self.min_native_families=int(min_native_families)
        self.inactive:dict[str,int]={}

    def run(self,brain:NeuroDecisionController,homeostasis:HomeostaticSupervisor,
            credit:CreditAssigner,memory:MultiTimescaleMemory,landscape:BrainStabilityLandscape,*,
            active_channels:Iterable[str],regime:str,validation_score:float|None=None,
            independent_families:int=0,allow_native_update:bool=False):
        active=set(active_channels);pruned=[];protected=[];contradictions=[];reasons=[]
        for key,ch in brain.channels.items():
            h=homeostasis._h(key)
            if key in active:
                self.inactive[key]=0;protected.append(key);continue
            self.inactive[key]=self.inactive.get(key,0)+1
            cr=credit.assess(key);ms=memory.state(key,regime)
            if cr.verdict in ("BENEFICIAL","HARMFUL") and ms.long_samples:
                # Strong learned evidence is retained for review, not forgotten merely for inactivity.
                protected.append(key);continue
            if h.lifecycle in (ChannelLifecycle.QUARANTINED,ChannelLifecycle.RETIRED):
                ch.conductance=max(.25,ch.conductance-self.prune_step);pruned.append(key);continue
            if self.inactive[key]>=self.stale_cycles and ch.conductance<=self.weak_conductance:
                ch.conductance=max(.25,ch.conductance-self.prune_step);pruned.append(key)

        # Contradiction: lifetime credit sign and current regime memory strongly disagree.
        for key in brain.channels:
            cr=credit.assess(key);ms=memory.state(key,regime)
            if cr.verdict=="BENEFICIAL" and ms.regime_samples and ms.regime_signal<-.25:
                contradictions.append(key)
            elif cr.verdict=="HARMFUL" and ms.regime_samples and ms.regime_signal>.25:
                contradictions.append(key)
        if contradictions:reasons.append("unresolved_memory_contradictions")

        native_updated=False
        if allow_native_update:
            if contradictions:reasons.append("native_update_blocked_by_contradiction")
            elif validation_score is None or validation_score<self.min_native_validation:
                reasons.append("native_update_requires_validation")
            elif independent_families<self.min_native_families:
                reasons.append("native_update_requires_independent_families")
            else:
                landscape.establish_native(brain,float(validation_score));native_updated=True
        return ConsolidationReport(tuple(sorted(set(pruned))),tuple(sorted(set(protected))),
                                   tuple(sorted(set(contradictions))),native_updated,tuple(reasons))
