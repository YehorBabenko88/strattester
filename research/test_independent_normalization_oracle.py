import random
import pytest
from research.independent_normalization_oracle import train_only_zscore

def test_test_distribution_never_refits_scaler():
    first, stats = train_only_zscore([1.,2.,3.], [4.,5.])
    second, other_stats = train_only_zscore([1.,2.,3.], [4.,5.,1e9])
    assert stats == other_stats
    assert first == second[:2]

def test_translation_and_positive_scale_invariance():
    rng = random.Random(72)
    for _ in range(200):
        train = [rng.uniform(-20,20) for _ in range(8)]
        test = [rng.uniform(-20,20) for _ in range(4)]
        a,_ = train_only_zscore(train,test)
        factor = rng.uniform(.5,5)
        offset = rng.uniform(-10,10)
        b,_ = train_only_zscore([factor*x+offset for x in train], [factor*x+offset for x in test])
        assert b == pytest.approx(a, abs=1e-12)

def test_constant_train_unseen_test_fails_closed():
    with pytest.raises(ValueError):
        train_only_zscore([2.,2.],[3.])
