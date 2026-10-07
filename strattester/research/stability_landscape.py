"""Stability landscape and recovery for the scientific brain.

Engineering abstraction inspired by protein energy landscapes: known-good controller
configurations are attractors; small perturbations remain in-basin; ambiguous
metastable states cannot execute; large/abnormal deviations trigger chaperone-like
recovery to a validated snapshot.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Mapping
from .neuro_controller import NeuroDecisionController
from .homeostasis import HomeostaticSupervisor,ChannelLifecycle

@dataclass(frozen=True)
class BrainSnapshot:
    conductance:tuple[tuple[str,float],...]
    adaptation:tuple[tuple[str,float],...]
    potential:float
    validation_score:float

@dataclass(frozen=True)
class StabilityReport:
    distance:float
    energy_gap:float
    in_basin:bool
    metastable:bool
    recover:bool
    reasons:tuple[str,...]

class BrainStabilityLandscape:
    def __init__(self,*,basin_radius=.45,min_energy_gap=.20,
                 metastable_margin=.08,recovery_radius=.90):
        self.basin_radius=float(basin_radius)
        self.min_energy_gap=float(min_energy_gap)
        self.metastable_margin=float(metastable_margin)
        self.recovery_radius=float(recovery_radius)
        self.native:BrainSnapshot|None=None

    def snapshot(self,c:NeuroDecisionController,validation_score:float=1.0):
        keys=sorted(c.channels)
        return BrainSnapshot(
            tuple((k,c.channels[k].conductance) for k in keys),
            tuple((k,c.channels[k].adaptation) for k in keys),
            c.potential,float(validation_score))

    def establish_native(self,c,validation_score:float):
        if validation_score<=0: raise ValueError("native state must be independently validated")
        self.native=self.snapshot(c,validation_score)
        return self.native

    def _distance(self,c):
        if self.native is None:return float("inf")
        ng=dict(self.native.conductance);na=dict(self.native.adaptation)
        keys=set(ng)|set(c.channels)
        terms=[]
        for k in keys:
            cur=c.channels.get(k)
            terms.append((getattr(cur,"conductance",1.0)-ng.get(k,1.0))**2)
            terms.append((getattr(cur,"adaptation",0.0)-na.get(k,0.0))**2)
        terms.append((c.potential-self.native.potential)**2)
        return sqrt(sum(terms)/max(1,len(terms)))

    def assess(self,c:NeuroDecisionController,*,alternative_score:float=0.0):
        d=self._distance(c)
        native_score=self.native.validation_score if self.native else 0.0
        gap=native_score-float(alternative_score)
        metastable=abs(gap)<self.metastable_margin
        in_basin=d<=self.basin_radius and gap>=self.min_energy_gap
        recover=d>=self.recovery_radius or gap<0
        reasons=[]
        if not in_basin:reasons.append("outside_native_basin")
        if metastable:reasons.append("metastable_ambiguity")
        if gap<self.min_energy_gap:reasons.append("insufficient_energy_gap")
        if recover:reasons.append("chaperone_recovery_required")
        return StabilityReport(d,gap,in_basin,metastable,recover,tuple(reasons))

    def recover(self,c:NeuroDecisionController,supervisor:HomeostaticSupervisor|None=None):
        if self.native is None:raise RuntimeError("no validated native state")
        ng=dict(self.native.conductance);na=dict(self.native.adaptation)
        # Unknown newly-created channels are quarantined instead of silently preserved.
        for k in list(c.channels):
            if k not in ng:
                if supervisor: supervisor._h(k).lifecycle=ChannelLifecycle.QUARANTINED
                c.channels[k].conductance=min(c.channels[k].conductance,.25)
                c.channels[k].adaptation=max(c.channels[k].adaptation,.75)
                continue
            c.channels[k].conductance=ng[k]
            c.channels[k].adaptation=na[k]
        c.potential=self.native.potential
        return self.snapshot(c,self.native.validation_score)

class PlasticityGate:
    """Changes are provisional until independent OOS validation earns consolidation."""
    def __init__(self,required_confirmations=3,max_step=.15):
        self.required_confirmations=int(required_confirmations)
        self.max_step=float(max_step);self.pending:dict[str,int]={}

    def propose(self,key,delta):
        delta=max(-self.max_step,min(self.max_step,float(delta)))
        self.pending.setdefault(key,0)
        return delta

    def confirm(self,key,success:bool):
        n=self.pending.get(key,0)
        n=n+1 if success else max(0,n-1)
        self.pending[key]=n
        return n>=self.required_confirmations

    def consolidate(self,c:NeuroDecisionController,key,delta):
        if self.pending.get(key,0)<self.required_confirmations:return False
        ch=c._channel(key)
        ch.conductance=max(.25,min(2.0,ch.conductance+self.propose(key,delta)))
        self.pending[key]=0
        return True
