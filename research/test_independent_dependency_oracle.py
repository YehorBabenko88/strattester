import pytest
from research.independent_dependency_oracle import validate_dependency_closure

def test_triangle_indirect_future_dependency_is_rejected():
    nodes = {'i':10,'j':10,'k':30,'pair_ij':10,'triangle_ij':10}
    edges = [('pair_ij','i'),('pair_ij','j'),('triangle_ij','pair_ij'),('triangle_ij','k')]
    with pytest.raises(ValueError, match='future'):
        validate_dependency_closure(nodes,edges,20)
    assert validate_dependency_closure(nodes,edges,30)['triangle_ij'] == 30

def test_cycles_and_missing_edges_fail_closed():
    with pytest.raises(ValueError, match='cyclic'):
        validate_dependency_closure({'a':0,'b':0}, [('a','b'),('b','a')],0)
    with pytest.raises(ValueError, match='unknown'):
        validate_dependency_closure({'a':0}, [('a','missing')],0)

def test_permutation_invariance():
    nodes = {'a':1,'b':2,'c':3}
    edges = [('c','a'),('c','b')]
    assert validate_dependency_closure(nodes,edges,3) == validate_dependency_closure(dict(reversed(list(nodes.items()))),list(reversed(edges)),3)
