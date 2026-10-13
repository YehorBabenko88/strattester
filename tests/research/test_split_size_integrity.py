import pytest
from strattester.research.validation import chronological_split

@pytest.mark.parametrize('sizes', [(-1, 2, 2), (2, -1, 2), (2, 2, -1), (0, 2, 2), (2, 0, 2), (2, 2, 0)])
def test_invalid_sizes_cannot_create_overlapping_or_empty_validation_splits(sizes):
    with pytest.raises(ValueError, match='sizes must be positive'):
        chronological_split(range(10), train_size=sizes[0], validation_size=sizes[1], test_size=sizes[2])
