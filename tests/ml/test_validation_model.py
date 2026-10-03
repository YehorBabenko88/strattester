from strattester.ml.validation import walk_forward_splits
from strattester.ml.model import LogisticBaseline

def test_walk_forward_keeps_purge_gap_and_chronology():
    splits=walk_forward_splits(30,train_size=10,test_size=5,purge=3,step=5)
    assert splits
    for s in splits:
        assert max(s.train)<min(s.test)
        assert min(s.test)-max(s.train)-1>=3

def test_logistic_baseline_learns_simple_directional_feature():
    rows=[{'x':float(i)} for i in range(-20,21) if i]
    labels=[1 if r['x']>0 else 0 for r in rows]
    m=LogisticBaseline(epochs=500).fit(rows,labels)
    assert m.predict_one({'x':10}).probability_up>.8
    assert m.predict_one({'x':-10}).probability_up<.2
    assert m.feature_importance()[0][0]=='x'
