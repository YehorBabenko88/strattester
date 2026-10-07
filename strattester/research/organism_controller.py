"""Integrated scientific organism controller.

Coordinates population health, evidence integration, stability landscape and
homeostatic execution gates. Every decision is explainable and fail-closed.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence,Mapping
from .scientific_graph import ScientificArtifact
from .neuro_controller import NeuroDecisionController,signals_from_artifacts,BrainDecision
from .homeostasis import HomeostaticSupervisor,HomeostaticDecision
from .stability_landscape import BrainStabilityLandscape,StabilityReport
from .population_guard import ModelIdentity,ModelPopulationGuard,PopulationReport

@dataclass(frozen=True)
class OrganismDecision:
    action:str
    permitted:bool
    brain:BrainDecision
    homeostasis:HomeostaticDecision
    population:PopulationReport
    stability:StabilityReport|None
    reasons:tuple[str,...]

class ScientificOrganismController:
    def __init__(self,brain:NeuroDecisionController|None=None,
                 homeostasis:HomeostaticSupervisor|None=None,
                 landscape:BrainStabilityLandscape|None=None,
                 population_guard:ModelPopulationGuard|None=None):
        self.brain=brain or NeuroDecisionController()
        self.homeostasis=homeostasis or HomeostaticSupervisor(self.brain)
        self.landscape=landscape or BrainStabilityLandscape()
        self.population_guard=population_guard or ModelPopulationGuard()
        self.history:list[OrganismDecision]=[]

    def establish_native(self,validation_score:float):
        return self.landscape.establish_native(self.brain,validation_score)

    def decide(self,artifacts:Sequence[ScientificArtifact],models:Sequence[ModelIdentity],*,
               external_permission:bool,inhibitory_veto:bool=False,
               risk:float=0.0,uncertainty:float=0.0,
               alternative_state_score:float=0.0):
        pop=self.population_guard.assess(models)
        reasons=list(pop.reasons)
        signals=signals_from_artifacts(artifacts)

        # Fail closed before integration if model ecology is unhealthy.
        permission=bool(external_permission and pop.healthy)
        if not pop.healthy:
            reasons.append("population_guard_block")

        stability=None
        if self.landscape.native is not None:
            stability=self.landscape.assess(self.brain,alternative_score=alternative_state_score)
            if stability.metastable:
                inhibitory_veto=True; reasons.append("metastable_veto")
            if stability.recover:
                self.landscape.recover(self.brain,self.homeostasis)
                inhibitory_veto=True; reasons.append("recovered_to_native_state")

        home=self.homeostasis.decide(signals,external_permission=permission,
                                     inhibitory_veto=inhibitory_veto,
                                     risk=risk,uncertainty=uncertainty)
        reasons.extend(home.vetoes)
        action=home.decision.action if home.permitted else "HOLD"
        out=OrganismDecision(action,home.permitted,home.decision,home,pop,stability,tuple(dict.fromkeys(reasons)))
        self.history.append(out)
        return out

    def learn_from_outcomes(self,outcomes:Mapping[str,float],rate=.05):
        for key,score in outcomes.items():
            self.homeostasis.note_outcome(key,float(score))
        return self.homeostasis.bounded_slow_modulate(outcomes,rate=rate)

    def last_decisions(self,n=20):
        return tuple(self.history[-max(0,int(n)):])
