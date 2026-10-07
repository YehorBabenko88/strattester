from strattester.research.brain_quorum import *

def test_majority_current_holder_can_execute():
    q=BrainQuorumFence(["a","b","c"])
    v=PartitionView("a",frozenset({"a","b"}),7,100)
    r=q.assess(v,BrainLease("a",7,200))
    assert r.majority and r.lease_valid and r.execution_allowed

def test_minority_partition_is_fenced_even_with_valid_looking_lease():
    q=BrainQuorumFence(["a","b","c"])
    v=PartitionView("a",frozenset({"a"}),7,100)
    r=q.assess(v,BrainLease("a",7,200))
    assert not r.execution_allowed and "no_majority_quorum" in r.reasons

def test_stale_epoch_is_fenced_after_failover():
    q=BrainQuorumFence(["a","b","c"])
    v=PartitionView("a",frozenset({"a","b","c"}),8,100)
    r=q.assess(v,BrainLease("a",7,200))
    assert not r.execution_allowed and "stale_epoch" in r.reasons

def test_non_holder_cannot_execute():
    q=BrainQuorumFence(["a","b","c"])
    v=PartitionView("b",frozenset({"a","b","c"}),4,100)
    r=q.assess(v,BrainLease("a",4,200))
    assert not r.execution_allowed and "not_lease_holder" in r.reasons

def test_expired_lease_is_fenced():
    q=BrainQuorumFence(["a","b","c"])
    v=PartitionView("a",frozenset({"a","b","c"}),4,200)
    assert not q.assess(v,BrainLease("a",4,200)).execution_allowed

def test_two_node_cluster_requires_both_members():
    q=BrainQuorumFence(["a","b"])
    assert q.quorum_size==2
    v=PartitionView("a",frozenset({"a"}),1,0)
    assert not q.assess(v,BrainLease("a",1,10)).execution_allowed


def test_old_membership_generation_is_fenced_even_with_majority_and_lease():
    q=BrainQuorumFence(["a","b","c"],membership_generation=9)
    v=PartitionView("a",frozenset({"a","b","c"}),7,100,membership_generation=8)
    r=q.assess(v,BrainLease("a",7,200))
    assert not r.execution_allowed and "stale_membership_generation" in r.reasons

def test_current_membership_generation_allows_normal_quorum():
    q=BrainQuorumFence(["a","b","c"],membership_generation=9)
    v=PartitionView("a",frozenset({"a","b"}),7,100,membership_generation=9)
    assert q.assess(v,BrainLease("a",7,200)).execution_allowed
