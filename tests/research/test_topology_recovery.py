from strattester.research.topology_recovery import *
from strattester.research.adaptive_role_allocator import WorkerNode,RoleRequest

def setup(cycles=2):
    r=ScientificTopologyRecovery(stabilization_cycles=cycles,stale_after_ms=100)
    ns=[WorkerNode("pc1",frozenset({"risk"}),domain="a"),
        WorkerNode("pc2",frozenset({"risk"}),domain="b")]
    req=[RoleRequest("risk","risk",critical=True)]
    return r,ns,req

def test_startup_requires_stabilization_before_execution():
    r,ns,req=setup(2)
    for n in ns:r.heartbeat(n.node_id,0)
    a=r.reconcile(ns,req,now_ms=10)
    assert a.state==RecoveryState.RECOVERING and not a.execution_allowed
    b=r.reconcile(ns,req,now_ms=20)
    assert b.state==RecoveryState.HEALTHY and b.execution_allowed

def test_worker_loss_immediately_degrades_and_adds_uncertainty():
    r,ns,req=setup(1)
    for n in ns:r.heartbeat(n.node_id,0)
    assert r.reconcile(ns,req,now_ms=10).execution_allowed
    r.heartbeat("pc1",200)
    x=r.reconcile(ns,req,now_ms=200)
    assert x.state==RecoveryState.DEGRADED and not x.execution_allowed
    assert "pc2" in x.lost_nodes and x.uncertainty_addon>0

def test_recovered_node_does_not_immediately_restore_permission():
    r,ns,req=setup(2)
    for n in ns:r.heartbeat(n.node_id,0)
    r.reconcile(ns,req,now_ms=1);r.reconcile(ns,req,now_ms=2)
    r.heartbeat("pc1",200)
    r.reconcile(ns,req,now_ms=200)
    r.heartbeat("pc2",201)
    x=r.reconcile(ns,req,now_ms=201)
    assert x.state==RecoveryState.RECOVERING and not x.execution_allowed
    y=r.reconcile(ns,req,now_ms=202)
    assert y.state==RecoveryState.HEALTHY and y.execution_allowed

def test_role_is_reallocated_to_independent_live_nodes():
    r=ScientificTopologyRecovery(stabilization_cycles=1,stale_after_ms=100)
    ns=[WorkerNode("a",frozenset({"risk"}),domain="1"),
        WorkerNode("b",frozenset({"risk"}),domain="2"),
        WorkerNode("c",frozenset({"risk"}),domain="3")]
    for n in ns:r.heartbeat(n.node_id,0)
    req=[RoleRequest("risk","risk",critical=True)]
    r.reconcile(ns,req,now_ms=1)
    r.heartbeat("a",200);r.heartbeat("c",200)
    x=r.reconcile(ns,req,now_ms=200)
    assert set(x.plan.placements["risk"].nodes)=={"a","c"}


def test_stale_heartbeat_cannot_move_clock_backwards():
    r=ScientificTopologyRecovery()
    assert r.heartbeat("a",100)
    assert not r.heartbeat("a",90)
    assert r._last_seen["a"]==100

def test_loss_of_noncritical_spare_does_not_permanently_block_execution():
    r=ScientificTopologyRecovery(stabilization_cycles=1)
    nodes=[WorkerNode("a",frozenset({"risk"}),domain="d1"),
           WorkerNode("b",frozenset({"risk"}),domain="d2"),
           WorkerNode("spare",frozenset({"other"}),domain="d3")]
    for n in nodes:r.heartbeat(n.node_id,100)
    req=[RoleRequest("risk","risk",critical=True)]
    assert r.reconcile(nodes,req,now_ms=100).execution_allowed
    r.heartbeat("a",19000);r.heartbeat("b",19000)
    report=r.reconcile(nodes,req,now_ms=20000)
    assert "spare" in report.lost_nodes
    assert report.plan.execution_healthy
    assert report.execution_allowed
    assert report.uncertainty_addon>0
