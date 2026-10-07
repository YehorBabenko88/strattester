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
from .decision_memory import DecisionMemory,DecisionTrace,ObservedOutcome,CounterfactualEstimate
from .credit_assignment import CreditAssigner
from .timescale_memory import MultiTimescaleMemory
from .stability_landscape import PlasticityGate
from .structural_mathematics import StructuralReport
from .structural_memory import StructuralMemory,StructuralExperience

@dataclass(frozen=True)
class OrganismDecision:
    action:str
    permitted:bool
    brain:BrainDecision
    homeostasis:HomeostaticDecision
    population:PopulationReport
    stability:StabilityReport|None
    reasons:tuple[str,...]
    structural_experience:StructuralExperience|None=None

class ScientificOrganismController:
    def __init__(self,brain:NeuroDecisionController|None=None,
                 homeostasis:HomeostaticSupervisor|None=None,
                 landscape:BrainStabilityLandscape|None=None,
                 population_guard:ModelPopulationGuard|None=None,
                 decision_memory:DecisionMemory|None=None,
                 credit_assigner:CreditAssigner|None=None,
                 timescale_memory:MultiTimescaleMemory|None=None,
                 plasticity_gate:PlasticityGate|None=None,
                 structural_memory:StructuralMemory|None=None):
        self.brain=brain or NeuroDecisionController()
        self.homeostasis=homeostasis or HomeostaticSupervisor(self.brain)
        self.landscape=landscape or BrainStabilityLandscape()
        self.population_guard=population_guard or ModelPopulationGuard()
        self.decision_memory=decision_memory or DecisionMemory()
        self.credit_assigner=credit_assigner or CreditAssigner()
        self.timescale_memory=timescale_memory or MultiTimescaleMemory()
        self.plasticity_gate=plasticity_gate or PlasticityGate()
        self.structural_memory=structural_memory or StructuralMemory()
        self.history:list[OrganismDecision]=[]

    def establish_native(self,validation_score:float):
        return self.landscape.establish_native(self.brain,validation_score)

    def decide(self,artifacts:Sequence[ScientificArtifact],models:Sequence[ModelIdentity],*,
               external_permission:bool,inhibitory_veto:bool=False,
               risk:float=0.0,uncertainty:float=0.0,
               alternative_state_score:float=0.0,
               structural_report:StructuralReport|None=None,
               structural_signature:str|None=None,
               require_structural_familiarity:bool=False):
        pop=self.population_guard.assess(models)
        reasons=list(pop.reasons)
        signals=signals_from_artifacts(artifacts)

        # Fail closed before integration if model ecology is unhealthy.
        permission=bool(external_permission and pop.healthy)
        if not pop.healthy:
            reasons.append("population_guard_block")

        structural_experience=None
        if structural_signature is not None:
            structural_experience=self.structural_memory.experience(structural_signature)
            if require_structural_familiarity:
                structural_ok,structural_reasons=self.structural_memory.execution_permission(structural_signature)
                if not structural_ok:
                    permission=False;reasons.extend(structural_reasons)

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
                                     risk=risk,uncertainty=uncertainty,
                                     structural_report=structural_report)
        reasons.extend(home.vetoes)
        action=home.decision.action if home.permitted else "HOLD"
        out=OrganismDecision(action,home.permitted,home.decision,home,pop,stability,tuple(dict.fromkeys(reasons)),structural_experience)
        self.history.append(out)
        return out

    def remember_decision(self,trace:DecisionTrace):
        self.decision_memory.remember(trace)

    def learn_decision(self,outcome:ObservedOutcome,channel_attribution:Mapping[str,float],*,
                       regime:str,counterfactuals:Sequence[CounterfactualEstimate]=()):
        self.decision_memory.observe(outcome)
        for cf in counterfactuals:self.decision_memory.estimate(cf)
        signal=self.decision_memory.learning_signal(outcome.decision_id,outcome.horizon)
        reports={}
        for key,attribution in channel_attribution.items():
            self.homeostasis.note_outcome(key,signal.realized_utility*float(attribution))
            self.timescale_memory.add(key,signal.realized_utility*float(attribution),regime)
            self.credit_assigner.add(key,signal,attribution=float(attribution))
            report=self.credit_assigner.assess(key);reports[key]=report
            candidate=self.timescale_memory.consolidation_candidate(key,regime)
            confirmed=report.verdict in ("BENEFICIAL","HARMFUL") and candidate is not None
            if self.plasticity_gate.confirm(key,confirmed):
                # Permanent change is based on conservative credit, not raw outcome.
                self.plasticity_gate.consolidate(self.brain,key,report.modulation)
        return reports

    def learn_from_outcomes(self,outcomes:Mapping[str,float],rate=.05):
        """Legacy bounded feedback path; prefer learn_decision for provenance-safe learning."""
        for key,score in outcomes.items():
            self.homeostasis.note_outcome(key,float(score))
        return self.homeostasis.bounded_slow_modulate(outcomes,rate=rate)

    def last_decisions(self,n=20):
        return tuple(self.history[-max(0,int(n)):])
