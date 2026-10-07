from strattester.research.scientific_graph import *

def test_graph_requires_existing_upstream():
    g=ScientificGraph()
    bad=ScientificArtifact("x","MODEL",("missing",),{},1)
    try:g.add(bad)
    except ValueError:pass
    else:raise AssertionError("orphan artifact accepted")

def test_layered_outputs_are_deterministic_and_traceable():
    xs=[((i%7)-3)/1000 for i in range(120)]
    g=ScientificGraph()
    o=g.add(observation_artifact(xs))
    v=g.add(volatility_artifact(o,xs))
    n=g.add(nonlinear_evidence_artifact(o,xs))
    r=g.add(regime_artifact(v,n))
    assert r.inputs==(v.artifact_id,n.artifact_id)
    assert observation_artifact(xs).artifact_id==o.artifact_id
    assert len(set(x.artifact_id for x in g.artifacts()))==4

def test_robustness_detects_parameter_regime_boundary():
    xs=[((i%5)-2)/100 for i in range(100)]
    o=observation_artifact(xs);v=volatility_artifact(o,xs)
    n=nonlinear_evidence_artifact(o,xs);r=regime_artifact(v,n)
    a=robustness_artifact(r,[{"regime":"A"},{"regime":"A"},{"regime":"B"}])
    assert a.payload["boundary_crossed"] is True
    assert a.payload["dominant_share"]==2/3
    assert a.confidence==2/3

def test_meta_pattern_consumes_multiple_model_results():
    a=ScientificArtifact("m1","REGIME",(),{"regime":"RISK_ON"},.8)
    b=ScientificArtifact("m2","REGIME",(),{"regime":"RISK_ON"},.7)
    c=ScientificArtifact("m3","REGIME",(),{"regime":"RISK_OFF"},.9)
    p=pattern_artifact([a,b,c])
    assert p.payload["consensus"]=="RISK_ON"
    assert p.payload["agreement"]==2/3
    assert p.inputs==(a.artifact_id,b.artifact_id,c.artifact_id)

def test_nonlinear_screen_never_claims_chaos():
    xs=[.01 if i%2 else -.01 for i in range(80)]
    o=observation_artifact(xs)
    n=nonlinear_evidence_artifact(o,xs)
    assert n.payload["chaos_claim"] is False
    assert n.warnings
