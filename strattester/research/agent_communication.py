"""Self-organizing communication fabric for scientific agents and Brain.

Combines direct signals with stigmergic shared-state cues. Links adapt from local
utility, reliability, latency and redundancy; positive reinforcement is bounded by
negative-feedback costs so no route can monopolize the network.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict,deque
from math import exp
from typing import Mapping,Iterable

@dataclass(frozen=True)
class AgentMessage:
    source:str
    target:str
    topic:str
    payload:object
    confidence:float
    timestamp_ms:int
    kind:str="signal"   # signal | cue

@dataclass
class LinkState:
    weight:float=1.0
    reliability:float=1.0
    latency_ms:float=0.0
    uses:int=0
    successes:int=0
    failures:int=0
    redundant:int=0

@dataclass(frozen=True)
class RouteChoice:
    source:str
    target:str
    score:float
    reason:str

class StigmergicBlackboard:
    def __init__(self,max_topics=256):
        self.max_topics=int(max_topics);self._state={};self._order=deque()

    def publish(self,topic:str,value:object,*,source:str,timestamp_ms:int,confidence:float):
        if topic not in self._state:self._order.append(topic)
        self._state[topic]=(value,source,int(timestamp_ms),max(0,min(1,float(confidence))))
        while len(self._order)>self.max_topics:
            old=self._order.popleft();self._state.pop(old,None)

    def cue(self,topic:str):
        return self._state.get(topic)

class SelfOrganizingCommunicationFabric:
    def __init__(self,*,min_weight=.15,max_weight=2.0,learning_rate=.08,
                 latency_scale_ms=500.0,redundancy_penalty=.15,max_neighbors=4):
        self.min_weight=float(min_weight);self.max_weight=float(max_weight)
        self.learning_rate=float(learning_rate);self.latency_scale_ms=float(latency_scale_ms)
        self.redundancy_penalty=float(redundancy_penalty);self.max_neighbors=int(max_neighbors)
        self.links:dict[tuple[str,str],LinkState]={}
        self.blackboard=StigmergicBlackboard()

    def link(self,a:str,b:str):
        return self.links.setdefault((a,b),LinkState())

    def observe_delivery(self,source:str,target:str,*,success:bool,latency_ms:float,
                         useful:float,redundant:bool=False):
        l=self.link(source,target);l.uses+=1
        if success:l.successes+=1
        else:l.failures+=1
        if redundant:l.redundant+=1
        # EWMA reliability and latency are local; no global coordinator needed.
        outcome=1.0 if success else 0.0
        l.reliability=.85*l.reliability+.15*outcome
        l.latency_ms=.8*l.latency_ms+.2*max(0,float(latency_ms))
        positive=max(-1,min(1,float(useful)))*l.reliability
        latency_cost=min(1,l.latency_ms/max(1,self.latency_scale_ms))
        redundancy_cost=self.redundancy_penalty if redundant else 0.0
        delta=self.learning_rate*(positive-latency_cost-redundancy_cost)
        l.weight=max(self.min_weight,min(self.max_weight,l.weight*exp(delta)))
        return l

    def route_score(self,source:str,target:str):
        l=self.link(source,target)
        latency_factor=1/(1+l.latency_ms/max(1,self.latency_scale_ms))
        failure_penalty=l.failures/max(1,l.uses)
        redundancy_penalty=self.redundancy_penalty*(l.redundant/max(1,l.uses))
        return max(0,l.weight*l.reliability*latency_factor*(1-failure_penalty)-redundancy_penalty)

    def neighbors(self,source:str,candidates:Iterable[str]):
        choices=[RouteChoice(source,t,self.route_score(source,t),"adaptive_local_link")
                 for t in candidates if t!=source]
        choices.sort(key=lambda x:(-x.score,x.target))
        return tuple(choices[:self.max_neighbors])

    def publish_cue(self,source:str,topic:str,payload:object,*,timestamp_ms:int,confidence:float):
        self.blackboard.publish(topic,payload,source=source,timestamp_ms=timestamp_ms,confidence=confidence)

    def should_direct_signal(self,source:str,target:str,*,urgency:float,topic_known:bool):
        score=self.route_score(source,target)
        # Direct communication for urgent/high-value local links; otherwise prefer shared cue.
        return bool(max(0,min(1,urgency))>=.7 and score>=.35) or (not topic_known and score>=.8)

    def anticipate_links(self,source:str,predicted_agents:Mapping[str,float],available:Iterable[str]):
        """Pre-warm only a sparse set of likely useful links; never create a dense all-to-all graph."""
        avail=set(available);ranked=[]
        for target,p in predicted_agents.items():
            if target==source or target not in avail:continue
            prior=self.route_score(source,target)
            ranked.append(RouteChoice(source,target,float(p)*(0.5+0.5*prior),"forecast_preconnect"))
        ranked.sort(key=lambda x:(-x.score,x.target))
        return tuple(ranked[:self.max_neighbors])

    def topology_health(self):
        if not self.links:return {"density":0.0,"dominance":0.0,"healthy":True}
        nodes=set(a for a,_ in self.links)|set(b for _,b in self.links)
        possible=max(1,len(nodes)*(len(nodes)-1))
        density=len(self.links)/possible
        weights=[max(0,l.weight) for l in self.links.values()];total=sum(weights)
        dominance=max(weights)/total if total else 0
        return {"density":density,"dominance":dominance,
                "healthy":density<=.65 and dominance<=.55}
