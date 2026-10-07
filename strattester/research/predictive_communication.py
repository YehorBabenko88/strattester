"""Bridge structural-state forecasts to adaptive agent/Brain communication."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Iterable
from .structural_state_graph import StructuralStateGraph,TransitionForecast
from .agent_communication import SelfOrganizingCommunicationFabric,RouteChoice

@dataclass(frozen=True)
class CommunicationPlan:
    state:str
    forecast:TransitionForecast
    predicted_agents:tuple[tuple[str,float],...]
    preconnect:tuple[RouteChoice,...]
    direct_to_brain:tuple[str,...]
    reasons:tuple[str,...]

class PredictiveCommunicationCoordinator:
    def __init__(self,state_graph:StructuralStateGraph,
                 fabric:SelfOrganizingCommunicationFabric,*,min_transition_probability=.15):
        self.state_graph=state_graph;self.fabric=fabric
        self.min_transition_probability=float(min_transition_probability)

    def plan(self,current_state:str,*,state_agents:Mapping[str,Iterable[str]],
             available_agents:Iterable[str],brain_id:str="brain"):
        forecast=self.state_graph.forecast(current_state)
        reasons=[]
        if not forecast.familiar:
            reasons.append("forecast_not_familiar")
            return CommunicationPlan(current_state,forecast,(),(),(),tuple(reasons))
        scores={}
        for state,p,_ in forecast.ranked:
            if p<self.min_transition_probability:continue
            for agent in state_agents.get(state,()):
                scores[agent]=max(scores.get(agent,0.0),p)
        ranked=tuple(sorted(scores.items(),key=lambda x:(-x[1],x[0])))
        preconnect=self.fabric.anticipate_links(brain_id,dict(ranked),available_agents)
        direct=[]
        for route in preconnect:
            urgency=min(1.0,route.score)
            if self.fabric.should_direct_signal(route.target,brain_id,
                                                urgency=urgency,topic_known=False):
                direct.append(route.target)
        if not preconnect:reasons.append("no_predictive_links")
        return CommunicationPlan(current_state,forecast,ranked,preconnect,
                                 tuple(sorted(set(direct))),tuple(reasons))

    def reinforce_plan(self,plan:CommunicationPlan,actual_state:str,*,latency_ms:Mapping[str,float]):
        predicted={s for s,_,_ in plan.forecast.ranked}
        hit=actual_state in predicted
        updates={}
        for route in plan.preconnect:
            useful=1.0 if hit else -.5
            updates[route.target]=self.fabric.observe_delivery(
                "brain",route.target,success=True,
                latency_ms=float(latency_ms.get(route.target,0)),
                useful=useful,redundant=not hit)
        return updates

    def publish_work_progress(self,agent_id:str,topic:str,payload:object,*,
                              timestamp_ms:int,confidence:float):
        """Stigmergic cue: agents coordinate via shared work-in-progress."""
        self.fabric.publish_cue(agent_id,topic,payload,timestamp_ms=timestamp_ms,
                                confidence=confidence)
