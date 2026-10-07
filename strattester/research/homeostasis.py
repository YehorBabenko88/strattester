"""Homeostatic supervision for the bio-inspired scientific controller.

Cancer biology is used here only as a systems-engineering analogy: healthy modules
remain dependent on external permission, preserve inhibitory checkpoints, cannot
self-amplify without bound, retire damaged clones, and are monitored for abnormal
autonomy. Protein-physics ideas add stable basins, chaperone-like recovery and a
two-stage specificity gate.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
from typing import Mapping,Sequence,Optional
from .neuro_controller import EvidenceSignal,BrainDecision,NeuroDecisionController
from .structural_mathematics import StructuralReport

class ChannelLifecycle(str,Enum):
    ACTIVE="ACTIVE"; SENESCENT="SENESCENT"; RETIRED="RETIRED"; QUARANTINED="QUARANTINED"

@dataclass
class ChannelHealth:
    lifecycle:ChannelLifecycle=ChannelLifecycle.ACTIVE
    age:int=0
    autonomous_drive:int=0
    failures:int=0
    successes:int=0
    mutations:int=0
    anomaly_score:float=0.0

@dataclass(frozen=True)
class HomeostaticDecision:
    decision:BrainDecision
    permitted:bool
    vetoes:tuple[str,...]
    quarantined:tuple[str,...]
    retired:tuple[str,...]
    structural:Optional[StructuralReport]=None

class HomeostaticSupervisor:
    def __init__(self,controller:NeuroDecisionController,*,max_conductance=1.6,
                 autonomous_limit=8,failure_retire=5,mutation_budget=3,
                 clone_share_limit=.55,anomaly_quarantine=.8):
        self.controller=controller
        self.max_conductance=float(max_conductance)
        self.autonomous_limit=int(autonomous_limit)
        self.failure_retire=int(failure_retire)
        self.mutation_budget=int(mutation_budget)
        self.clone_share_limit=float(clone_share_limit)
        self.anomaly_quarantine=float(anomaly_quarantine)
        self.health:dict[str,ChannelHealth]={}

    def _h(self,key): return self.health.setdefault(key,ChannelHealth())

    def note_model_change(self,key):
        h=self._h(key);h.mutations+=1
        if h.mutations>self.mutation_budget:h.lifecycle=ChannelLifecycle.QUARANTINED
        return h.lifecycle

    def note_outcome(self,key,score:float):
        h=self._h(key);h.age+=1
        if score>0:h.successes+=1;h.failures=max(0,h.failures-1)
        elif score<0:h.failures+=1
        if h.failures>=self.failure_retire:h.lifecycle=ChannelLifecycle.RETIRED
        return h.lifecycle

    def inspect_autonomy(self,signals:Sequence[EvidenceSignal],external_permission:bool):
        for s in signals:
            h=self._h(s.source_id)
            if abs(s.direction)*s.strength>=.8 and not external_permission:
                h.autonomous_drive+=1
            else:
                h.autonomous_drive=max(0,h.autonomous_drive-1)
            if h.autonomous_drive>self.autonomous_limit:
                h.lifecycle=ChannelLifecycle.SENESCENT

    def immune_surveillance(self,signals:Sequence[EvidenceSignal]):
        quarantined=[]
        for s in signals:
            h=self._h(s.source_id)
            # Strong direction with poor confidence/robustness is abnormal autonomy.
            h.anomaly_score=max(0.0,min(1.0,abs(s.direction)*s.strength*(1-s.confidence*s.robustness)))
            if h.anomaly_score>=self.anomaly_quarantine:
                h.lifecycle=ChannelLifecycle.QUARANTINED;quarantined.append(s.source_id)
        return tuple(quarantined)

    def _filter(self,signals):
        return tuple(s for s in signals if self._h(s.source_id).lifecycle==ChannelLifecycle.ACTIVE)

    def _clone_dominance_veto(self,signals):
        total=sum(max(0,s.strength*s.confidence*s.robustness) for s in signals)
        if total<=0:return False
        shares=[s.strength*s.confidence*s.robustness/total for s in signals]
        return bool(shares and max(shares)>self.clone_share_limit and len(signals)>1)

    def decide(self,signals:Sequence[EvidenceSignal],*,external_permission:bool,
               inhibitory_veto:bool=False,risk=0.0,uncertainty=0.0,
               structural_report:Optional[StructuralReport]=None):
        self.inspect_autonomy(signals,external_permission)
        quarantined=self.immune_surveillance(signals)
        active=self._filter(signals)
        vetoes=[]
        if not external_permission:vetoes.append("missing_external_permission")
        if inhibitory_veto:vetoes.append("inhibitory_checkpoint")
        # Structural mathematics is an independent safety sieve. A fragile,
        # unbalanced, incomplete or collapsed scientific structure may be
        # observed and learned from, but it may not actuate the Brain.
        if structural_report is not None and not structural_report.healthy:
            vetoes.extend(f"structural:{r}" for r in structural_report.reasons)
        if self._clone_dominance_veto(active):vetoes.append("clone_dominance")
        raw=self.controller.integrate(active,risk=risk,uncertainty=uncertainty)
        # Second sieve: activation is necessary but not sufficient for execution.
        permitted=raw.action!="HOLD" and not vetoes
        if not permitted and raw.action!="HOLD":
            from .neuro_controller import BrainDecision
            raw=BrainDecision(raw.state,"HOLD",raw.membrane_potential,raw.threshold,
                              raw.excitation,raw.inhibition,raw.confidence,
                              raw.reasons+tuple(vetoes))
        retired=tuple(k for k,h in self.health.items() if h.lifecycle==ChannelLifecycle.RETIRED)
        return HomeostaticDecision(raw,permitted,tuple(vetoes),quarantined,retired,structural_report)

    def bounded_slow_modulate(self,outcomes:Mapping[str,float],rate=.05):
        values=self.controller.slow_modulate(outcomes,rate)
        for key in list(values):
            c=self.controller.channels[key]
            c.conductance=min(self.max_conductance,c.conductance)
            if self._h(key).lifecycle is not ChannelLifecycle.ACTIVE:
                c.conductance=min(c.conductance,.5)
            values[key]=c.conductance
        return values
