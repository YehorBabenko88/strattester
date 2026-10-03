import math
import pytest

from strattester.ml.model import LogisticBaseline


def test_fit_uses_union_of_sparse_feature_keys():
    rows = [
        {"base": 1.0},
        {"base": 2.0, "late_feature": 10.0},
        {"base": 3.0, "late_feature": 20.0},
        {"base": 4.0, "late_feature": 30.0},
    ]
    model = LogisticBaseline(epochs=5).fit(rows, [0, 0, 1, 1])
    assert model.feature_names == ("base", "late_feature")
    assert dict(model.coefficients()).keys() == {"base", "late_feature"}


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_fit_rejects_non_finite_features(bad):
    with pytest.raises(ValueError, match="must be finite"):
        LogisticBaseline(epochs=1).fit([{"x": 1.0}, {"x": bad}], [0, 1])


def test_predict_rejects_non_finite_features():
    model = LogisticBaseline(epochs=1).fit([{"x": 1.0}, {"x": 2.0}], [0, 1])
    with pytest.raises(ValueError, match="must be finite"):
        model.predict_one({"x": math.nan})
