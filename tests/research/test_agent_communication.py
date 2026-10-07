from strattester.research.agent_communication import *

def test_useful_fast_link_reinforces():
    f=SelfOrganizingCommunicationFabric()
    before=f.link("a","brain").weight
    for _ in range(5):f.observe_delivery("a","brain",success=True,latency_ms=10,useful=1)
    assert f.link("a","brain").weight>before

def test_slow_failed_redundant_link_weakens():
    f=SelfOrganizingCommunicationFabric()
    before=f.link("a","brain").weight
    for _ in range(5):f.observe_delivery("a","brain",success=False,latency_ms=2000,useful=-1,redundant=True)
    assert f.link("a","brain").weight<before
    assert f.link("a","brain").weight>=f.min_weight

def test_neighbors_are_sparse_and_ranked():
    f=SelfOrganizingCommunicationFabric(max_neighbors=2)
    for t,u in [("b",1),("c",.5),("d",-1)]:
        f.observe_delivery("a",t,success=True,latency_ms=10,useful=u)
    ns=f.neighbors("a",["b","c","d"])
    assert len(ns)==2 and ns[0].score>=ns[1].score

def test_stigmergic_blackboard_is_bounded():
    b=StigmergicBlackboard(max_topics=2)
    b.publish("x",1,source="a",timestamp_ms=1,confidence=1)
    b.publish("y",2,source="b",timestamp_ms=2,confidence=1)
    b.publish("z",3,source="c",timestamp_ms=3,confidence=1)
    assert b.cue("x") is None and b.cue("z")[0]==3

def test_urgent_good_link_prefers_direct_signal():
    f=SelfOrganizingCommunicationFabric()
    assert f.should_direct_signal("a","brain",urgency=.9,topic_known=True)

def test_anticipation_does_not_create_dense_mesh():
    f=SelfOrganizingCommunicationFabric(max_neighbors=3)
    pred={f"a{i}":1/(i+1) for i in range(10)}
    out=f.anticipate_links("brain",pred,pred)
    assert len(out)==3

def test_topology_detects_single_link_dominance():
    f=SelfOrganizingCommunicationFabric()
    f.link("a","brain").weight=2
    f.link("b","brain").weight=.15
    h=f.topology_health()
    assert h["dominance"]>.55 and not h["healthy"]
