import pytest
from strattester.research.causal import CausalFeature,CausalView

def test_view_hides_features_not_yet_known():
    xs=[CausalFeature(100,120,'pivot',1,'v1'),CausalFeature(110,110,'close',2,'v1')]
    assert [x.kind for x in CausalView(xs).at(115)]==['close']

def test_feature_rejects_known_before_event():
    with pytest.raises(ValueError):
        CausalFeature(120,119,'bad',1,'v1')

def test_future_append_does_not_change_past_view():
    prefix=[CausalFeature(100,100,'close',1,'v1'),CausalFeature(110,130,'pivot',2,'v1')]
    before=CausalView(prefix).at(120)
    after=CausalView(prefix+[CausalFeature(140,140,'close',3,'v1')]).at(120)
    assert before==after
