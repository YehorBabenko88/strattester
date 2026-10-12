from pathlib import Path
from strattester.runtime.grid_handoff import write_handoff

def test_handoff_requires_science_bundle(tmp_path):
    science=tmp_path/"science.json";science.write_text('{"x":1}',encoding="utf-8")
    out=write_handoff(tmp_path/"handoff.json",science)
    assert out["ready_for_grid_import"] is True
    assert out["science_bundle"]["sha256"]
    assert (tmp_path/"handoff.json").exists()


def test_handoff_rejects_empty_science_bundle(tmp_path):
    import pytest
    science = tmp_path / "science.json"
    science.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        write_handoff(tmp_path / "handoff.json", science)
    assert not (tmp_path / "handoff.json").exists()


def test_handoff_never_overwrites_science_bundle(tmp_path):
    import pytest
    science = tmp_path / "science.json"
    science.write_text('{"x":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="overwrite"):
        write_handoff(science, science)
    assert science.read_text(encoding="utf-8") == '{"x":1}'
