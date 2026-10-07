from strattester.research.scientific_fleet import *
from strattester.research.adaptive_role_allocator import WorkerNode,RoleRequest

def test_healthy_independent_critical_replicas_allow_permission():
    c=ScientificFleetCoordinator()
    p=c.plan([WorkerNode("a",frozenset({"risk"}),domain="pc1"),
              WorkerNode("b",frozenset({"risk"}),domain="pc2")],
             [RoleRequest("risk","risk",critical=True)])
    assert p.execution_healthy
    assert c.permission(p,True)[0]

def test_missing_critical_replica_blocks_permission():
    c=ScientificFleetCoordinator()
    p=c.plan([WorkerNode("a",frozenset({"risk"}),domain="pc1")],
             [RoleRequest("risk","risk",critical=True)])
    ok,reasons=c.permission(p,True)
    assert not ok and any(r.startswith("fleet:risk:") for r in reasons)

def test_external_permission_remains_authoritative():
    c=ScientificFleetCoordinator()
    p=c.plan([WorkerNode("a",frozenset({"risk"}),domain="pc1"),
              WorkerNode("b",frozenset({"risk"}),domain="pc2")],
             [RoleRequest("risk","risk",critical=True)])
    assert c.permission(p,False)==(False,("external_permission_denied",))
