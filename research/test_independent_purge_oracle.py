import random
import pytest
from research.independent_purge_oracle import validate_disjoint_labels

def test_touching_label_boundaries_are_overlap():
    with pytest.raises(ValueError):
        validate_disjoint_labels([(0,10)], [(10,20)])
    assert validate_disjoint_labels([(0,10)], [(11,20)])

def test_embargo_is_symmetric():
    with pytest.raises(ValueError):
        validate_disjoint_labels([(0,10)], [(12,20)], embargo_ns=2)
    with pytest.raises(ValueError):
        validate_disjoint_labels([(12,20)], [(0,10)], embargo_ns=2)

def test_randomized_translation_invariance():
    rng = random.Random(42)
    for _ in range(200):
        left = rng.randint(0,10000)
        right = left + rng.randint(0,100)
        gap = rng.randint(0,100)
        embargo = rng.randint(0,10)
        train, test = [(left,right)], [(right+gap+1,right+gap+50)]
        allowed = gap >= embargo
        if allowed:
            assert validate_disjoint_labels(train,test,embargo)
            assert validate_disjoint_labels([(a+1000,b+1000) for a,b in train], [(a+1000,b+1000) for a,b in test],embargo)
        else:
            with pytest.raises(ValueError):
                validate_disjoint_labels(train,test,embargo)
