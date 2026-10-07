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


def test_multi_role_allocation_reserves_capacity():
    a=AdaptiveRoleAllocator(max_load=.9)
    ns=[WorkerNode("a",frozenset({"x"}),load=.55,capacity_cost=.25),
        WorkerNode("b",frozenset({"x"}),load=.60,capacity_cost=.25)]
    ps=a.allocate([RoleRequest("r1","x"),RoleRequest("r2","x")],ns)
    assert ps["r1"].nodes==("a",)
    assert ps["r2"].nodes==("b",)

def test_communication_quality_affects_placement():
    a=AdaptiveRoleAllocator()
    ns=[WorkerNode("poor-link",frozenset({"x"}),communication_quality=.2),
        WorkerNode("good-link",frozenset({"x"}),communication_quality=.95,latency_ms=20)]
    assert a.place(RoleRequest("r","x"),ns).nodes==("good-link",)

def test_invalid_node_telemetry_is_excluded():
    a=AdaptiveRoleAllocator()
    bad=[WorkerNode("neg-load",frozenset({"x"}),load=-.1),
         WorkerNode("nan",frozenset({"x"}),latency_ms=float("nan")),
         WorkerNode("bad-failure",frozenset({"x"}),failure_rate=2)]
    p=a.place(RoleRequest("r","x"),bad)
    assert p.degraded and not p.nodes
