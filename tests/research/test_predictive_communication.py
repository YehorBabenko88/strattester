from strattester.research.structural_state_graph import StructuralStateGraph
from strattester.research.agent_communication import SelfOrganizingCommunicationFabric
from strattester.research.predictive_communication import PredictiveCommunicationCoordinator

def familiar_graph():
    g=StructuralStateGraph(min_transition_samples=2,min_confidence=.3)
    for s in ["A","B","A","B","A","C","A","B"]:g.observe(s,regime="R")
    return g

def test_forecast_prepares_agents_for_likely_next_states():
    g=familiar_graph();f=SelfOrganizingCommunicationFabric(max_neighbors=2)
    c=PredictiveCommunicationCoordinator(g,f,min_transition_probability=.2)
    p=c.plan("A",state_agents={"B":["trend","vol"],"C":["chaos"]},
             available_agents=["trend","vol","chaos"])
    assert p.forecast.familiar
    assert p.preconnect
    assert any(a=="trend" for a,_ in p.predicted_agents)

def test_unfamiliar_forecast_does_not_preconnect():
    g=StructuralStateGraph(min_transition_samples=5)
    g.observe("A",regime="R");g.observe("B",regime="R")
    c=PredictiveCommunicationCoordinator(g,SelfOrganizingCommunicationFabric())
    p=c.plan("A",state_agents={"B":["trend"]},available_agents=["trend"])
    assert not p.preconnect and "forecast_not_familiar" in p.reasons

def test_wrong_prediction_weakens_prepared_links():
    g=familiar_graph();f=SelfOrganizingCommunicationFabric(max_neighbors=2)
    c=PredictiveCommunicationCoordinator(g,f,min_transition_probability=.2)
    p=c.plan("A",state_agents={"B":["trend"],"C":["chaos"]},
             available_agents=["trend","chaos"])
    before={r.target:f.link("brain",r.target).weight for r in p.preconnect}
    c.reinforce_plan(p,"Z",latency_ms={})
    assert all(f.link("brain",t).weight<=w for t,w in before.items())

def test_stigmergic_progress_is_visible_without_direct_message():
    g=familiar_graph();f=SelfOrganizingCommunicationFabric()
    c=PredictiveCommunicationCoordinator(g,f)
    c.publish_work_progress("agent1","regime:R",{"done":.5},timestamp_ms=10,confidence=.8)
    cue=f.blackboard.cue("regime:R")
    assert cue[0]=={"done":.5} and cue[1]=="agent1"
