"""Bio-inspired decision controller for scientific artifacts.

This is a computational abstraction of excitable membranes/receptor kinetics, not a
biophysical simulation. Evidence channels integrate over time; excitation and
inhibition compete; activation requires a threshold; refractory/desensitized states
prevent repeated firing; slow modulators alter future sensitivity.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
from math import exp,tanh
from typing import Mapping,Sequence
from .scientific_graph import ScientificArtifact

class BrainState(str,Enum):
    RESTING="RESTING"; INTEGRATING="INTEGRATING"; ACTIVATED="ACTIVATED"
    REFRACTORY="REFRACTORY"; DESENSITIZED="DESENSITIZED"

@dataclass(frozen=True)
class EvidenceSignal:
    source_id:str
    direction:float       # -1 bearish/inhibitory .. +1 bullish/excitatory
    strength:float        # 0..1
    confidence:float      # 0..1
    robustness:float=1.0  # parameter/OOS stability
    novelty:float=1.0     # suppress repeated identical evidence

@dataclass
class ChannelMemory:
    conductance:float=1.0
    adaptation:float=0.0
    last_drive:float=0.0

@dataclass(frozen=True)
class BrainDecision:
    state:BrainState
    action:str
    membrane_potential:float
    threshold:float
    excitation:float
    inhibition:float
    confidence:float
    reasons:tuple[str,...]

class NeuroDecisionController:
    def __init__(self,*,threshold=.62,leak=.18,refractory_steps=3,
                 desensitize_at=.85,conflict_penalty=.45):
        self.base_threshold=float(threshold); self.leak=float(leak)
        self.refractory_steps=int(refractory_steps)
        self.desensitize_at=float(desensitize_at)
        self.conflict_penalty=float(conflict_penalty)
        self.potential=0.0; self.state=BrainState.RESTING
        self._refractory=0; self.channels:dict[str,ChannelMemory]={}

    def _channel(self,key): return self.channels.setdefault(key,ChannelMemory())

    def integrate(self,signals:Sequence[EvidenceSignal],*,risk=0.0,uncertainty=0.0):
        if self._refractory>0:
            self._refractory-=1; self.potential*=1-self.leak
            self.state=BrainState.REFRACTORY
            return BrainDecision(self.state,"HOLD",self.potential,self.base_threshold,0,0,0,
                                 ("refractory_gate",))
        ex=inh=weighted=0.0; weight=0.0; reasons=[]
        for s in signals:
            c=self._channel(s.source_id)
            reliability=max(0,min(1,s.confidence))*max(0,min(1,s.robustness))
            drive=max(-1,min(1,s.direction))*max(0,min(1,s.strength))*reliability*max(0,min(1,s.novelty))
            effective=drive*c.conductance*(1-c.adaptation)
            if effective>=0: ex+=effective
            else: inh+=-effective
            weighted+=effective; weight+=abs(effective)
            c.last_drive=drive
            # sustained strong evidence desensitizes its own channel
            if abs(drive)>=self.desensitize_at:c.adaptation=min(.9,c.adaptation+.12)
            else:c.adaptation=max(0,c.adaptation-.04)
            reasons.append(f"{s.source_id}:{effective:+.3f}")
        conflict=min(ex,inh)/(max(ex,inh)+1e-12) if max(ex,inh)>0 else 0.0
        net=weighted*(1-self.conflict_penalty*conflict)
        self.potential=(1-self.leak)*self.potential+net
        dynamic_threshold=self.base_threshold*(1+max(0,risk)+max(0,uncertainty))
        conf=(abs(weighted)/(weight+1e-12))*(1-conflict) if weight else 0.0
        if abs(self.potential)>=dynamic_threshold:
            self.state=BrainState.ACTIVATED
            action="LONG" if self.potential>0 else "SHORT"
            self._refractory=self.refractory_steps
        else:
            self.state=BrainState.INTEGRATING if signals else BrainState.RESTING
            action="HOLD"
        return BrainDecision(self.state,action,self.potential,dynamic_threshold,ex,inh,conf,
                             tuple(reasons))

    def slow_modulate(self,outcomes:Mapping[str,float],rate=.05):
        """Homeostatic/reinforcement-like slow modulation, bounded to avoid runaway."""
        for key,outcome in outcomes.items():
            c=self._channel(key)
            c.conductance=max(.25,min(2.0,c.conductance*exp(rate*max(-1,min(1,float(outcome))))))
        return {k:v.conductance for k,v in self.channels.items()}

def signals_from_artifacts(artifacts:Sequence[ScientificArtifact]):
    """Adapter: only artifacts with explicit signed evidence may drive decisions."""
    out=[]
    for a in artifacts:
        p=a.payload
        if "direction" not in p: continue
        out.append(EvidenceSignal(a.artifact_id,float(p["direction"]),
          float(p.get("strength",1)),float(a.confidence),
          float(p.get("robustness",p.get("dominant_share",1))),
          float(p.get("novelty",1))))
    return tuple(out)
