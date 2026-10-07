"""Population/lineage safeguards for scientific model evolution."""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter,defaultdict
from typing import Iterable

@dataclass(frozen=True)
class ModelIdentity:
    model_id:str
    family:str
    lineage:str
    generation:int=0
    parent_id:str|None=None

@dataclass(frozen=True)
class PopulationReport:
    diversity:float
    largest_lineage_share:float
    mutation_rate:float
    independent_families:int
    healthy:bool
    reasons:tuple[str,...]

class ModelPopulationGuard:
    def __init__(self,*,min_diversity=.45,max_lineage_share=.6,max_mutation_rate=.25,
                 min_independent_families=2):
        self.min_diversity=float(min_diversity);self.max_lineage_share=float(max_lineage_share)
        self.max_mutation_rate=float(max_mutation_rate)
        self.min_independent_families=int(min_independent_families)

    def assess(self,models:Iterable[ModelIdentity]):
        ms=list(models);n=len(ms)
        if not n:return PopulationReport(0,0,0,0,False,("empty_population",))
        line=Counter(m.lineage for m in ms);fam=Counter(m.family for m in ms)
        diversity=len(line)/n
        largest=max(line.values())/n
        mutated=sum(m.generation>0 for m in ms)/n
        reasons=[]
        if diversity<self.min_diversity:reasons.append("low_lineage_diversity")
        if largest>self.max_lineage_share:reasons.append("clonal_expansion")
        if mutated>self.max_mutation_rate:reasons.append("excess_mutation_rate")
        if len(fam)<self.min_independent_families:reasons.append("insufficient_independent_families")
        return PopulationReport(diversity,largest,mutated,len(fam),not reasons,tuple(reasons))

    @staticmethod
    def independent_confirmation(candidate:ModelIdentity,validators:Iterable[ModelIdentity]):
        """A descendant/same lineage cannot independently validate its relative."""
        return tuple(v for v in validators
                     if v.model_id!=candidate.model_id
                     and v.lineage!=candidate.lineage
                     and v.family!=candidate.family)

    @staticmethod
    def consensus_weights(models:Iterable[ModelIdentity]):
        """Each lineage receives equal total vote mass, preventing clone vote stuffing."""
        ms=list(models);groups=defaultdict(list)
        for m in ms:groups[m.lineage].append(m)
        if not groups:return {}
        lineage_mass=1/len(groups)
        return {m.model_id:lineage_mass/len(groups[m.lineage]) for m in ms}
