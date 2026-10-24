import numpy as np
import pytest
from research.independent_numpy_oracles import masked_attention_reference, triangle_outgoing_reference

def test_masked_attention_excludes_future_and_fully_masked_rows():
    q = [[1., 0.], [0., 1.]]
    k = [[1., 0.], [0., 1.], [100., 100.]]
    v = [[2., 3.], [4., 5.], [1e8, 1e8]]
    mask = [[True, False, False], [False, False, False]]
    actual = masked_attention_reference(q, k, v, mask)
    np.testing.assert_allclose(actual, [[2, 3], [0, 0]], rtol=0, atol=1e-12)
    v[2] = [-1e8, -1e8]
    np.testing.assert_allclose(masked_attention_reference(q, k, v, mask), actual)

def test_triangle_outgoing_orientation_and_mask():
    pair = np.zeros((3, 3, 1))
    pair[0, 2, 0] = 2
    pair[1, 2, 0] = 3
    pair[2, 0, 0] = 99
    mask = np.ones((3, 3), dtype=bool)
    result = triangle_outgoing_reference(pair, mask)
    assert result[0, 1, 0] == 6
    mask[1, 2] = False
    assert triangle_outgoing_reference(pair, mask)[0, 1, 0] == 0

def test_attention_rejects_invalid_mask():
    with pytest.raises(ValueError):
        masked_attention_reference([[1., 2.]], [[1., 2.]], [[1.]], [[1]])
