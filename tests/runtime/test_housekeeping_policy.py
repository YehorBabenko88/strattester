import os

import pytest

from strattester.runtime.housekeeping import cleanup_artifacts


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
@pytest.mark.parametrize('parameter', ['now', 'older_than_seconds'])
def test_nonfinite_cleanup_policy_rejected_without_deleting_files(tmp_path, parameter, value):
    candidate = tmp_path / 'research.stage'
    candidate.write_bytes(b'preserve')
    os.utime(candidate, (100, 100))
    policy = {'now': 1000, 'older_than_seconds': 50, parameter: value}

    with pytest.raises(ValueError, match='invalid cleanup policy'):
        cleanup_artifacts(tmp_path, **policy)

    assert candidate.read_bytes() == b'preserve'
