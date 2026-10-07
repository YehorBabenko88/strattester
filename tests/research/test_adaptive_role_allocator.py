from strattester.research.adaptive_role_allocator import *

def test_best_healthy_capable_node_selected():
    a=AdaptiveRoleAllocator()
    ns=[WorkerNode("slow",frozenset({"vol"}),latency_ms=500),
        WorkerNode("fast",frozenset({"vol"}),latency_ms=10)]
    p=a.place(RoleRequest("volatility","vol"),ns)
    assert p.nodes==("fast",) and not p.degraded

def test_unhealthy_or_overloaded_nodes_are_excluded():
    a=AdaptiveRoleAllocator()
    ns=[WorkerNode("bad",frozenset({"x"}),healthy=False),
        WorkerNode("busy",frozenset({"x"}),load=.99)]
    p=a.place(RoleRequest("x","x"),ns)
    assert p.degraded and "no_healthy_capable_node" in p.reasons

def test_critical_role_prefers_independent_failure_domains():
    a=AdaptiveRoleAllocator()
    ns=[WorkerNode("a",frozenset({"risk"}),domain="pc1"),
        WorkerNode("b",frozenset({"risk"}),domain="pc1"),
        WorkerNode("c",frozenset({"risk"}),domain="pc2",latency_ms=50)]
    p=a.place(RoleRequest("risk","risk",critical=True),ns)
    assert len(p.nodes)==2
    assert set(p.nodes)=={"a","c"}
    assert not p.degraded

def test_critical_role_reports_insufficient_redundancy():
    a=AdaptiveRoleAllocator()
    p=a.place(RoleRequest("risk","risk",critical=True),
              [WorkerNode("a",frozenset({"risk"}),domain="pc1")])
    assert p.degraded and "insufficient_redundancy" in p.reasons

def test_execution_health_fails_closed_for_degraded_critical_role():
    a=AdaptiveRoleAllocator()
    ps=a.allocate([RoleRequest("risk","risk",critical=True)],
                  [WorkerNode("a",frozenset({"risk"}))])
    ok,reasons=a.execution_health(ps,["risk"])
    assert not ok and reasons
