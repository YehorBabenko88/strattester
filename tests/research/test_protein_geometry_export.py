import json
import pytest
from strattester.research.protein_geometry_export import geometry_payload, export_json


def test_payload_alignment_and_bound():
    closes = [100 + i for i in range(50)]
    times = [i * 60 for i in range(50)]
    result = geometry_payload(closes, times, window=4, max_points=7)
    assert len(result["points"]) == 7
    assert result["timestamps"] == times[-7:]
    assert result["closes"] == closes[-7:]
    assert len(result["distances"]) == 7
    assert result["mode"] == "OFFLINE_RESEARCH_ONLY"


def test_prefix_invariance():
    prices = [100 + i for i in range(30)]
    times = list(range(30))
    a = geometry_payload(prices, times, window=4)
    b = geometry_payload(prices + [1000], times + [30], window=4)
    assert b["points"][:len(a["points"])] == a["points"]


def test_export_never_overwrites(tmp_path):
    path = tmp_path / "geometry.json"
    export_json(path, [1, 2, 3, 4], [1, 2, 3, 4], window=2)
    assert json.loads(path.read_text())["schema"] == "strattester.protein_geometry.v1"
    with pytest.raises(FileExistsError):
        export_json(path, [1, 2, 3, 4], [1, 2, 3, 4], window=2)


@pytest.mark.parametrize("timestamps", [[0, 1, 1, 3], [0, 3, 2, 4], [-1, 1, 2, 3]])
def test_bad_timestamps(timestamps):
    with pytest.raises(ValueError):
        geometry_payload([1, 2, 3, 4], timestamps, window=2)
