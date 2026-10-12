from pathlib import Path
from strattester.runtime.grid_handoff import write_handoff, verify_handoff, pack_handoff

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


def test_handoff_verifies_science_checksum(tmp_path):
    import pytest
    science = tmp_path / "science.json"
    science.write_text('{"x":1}', encoding="utf-8")
    manifest = tmp_path / "handoff.json"
    write_handoff(manifest, science)
    assert verify_handoff(manifest)["ready_for_grid_import"] is True
    science.write_text('{"x":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_handoff(manifest)


def test_handoff_rejects_missing_science_payload(tmp_path):
    import pytest
    science = tmp_path / "science.json"
    science.write_text('{"x":1}', encoding="utf-8")
    manifest = tmp_path / "handoff.json"
    write_handoff(manifest, science)
    science.unlink()
    with pytest.raises(ValueError, match="missing or empty"):
        verify_handoff(manifest)


def test_verify_handoff_accepts_relative_payload_after_copy(tmp_path):
    import json
    science = tmp_path / "science.json"
    science.write_text('{"x":1}', encoding="utf-8")
    manifest = tmp_path / "handoff.json"
    data = write_handoff(manifest, science)
    data["science_bundle"]["path"] = "science.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert verify_handoff(manifest)["ready_for_grid_import"] is True


def test_verify_handoff_rejects_non_object_json(tmp_path):
    import pytest
    manifest = tmp_path / "handoff.json"
    manifest.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        verify_handoff(manifest)


def test_handoff_paths_are_absolute_even_for_relative_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    science = Path("science.json")
    science.write_text('{"x":1}', encoding="utf-8")
    out = write_handoff("handoff.json", science)
    assert Path(out["science_bundle"]["path"]).is_absolute()
    assert verify_handoff(tmp_path / "handoff.json")["ready_for_grid_import"] is True


def test_pack_handoff_survives_source_removal(tmp_path):
    science = tmp_path / "science.json"
    science.write_text('{"x":1}', encoding="utf-8")
    original = tmp_path / "source-handoff.json"
    write_handoff(original, science)
    packaged = pack_handoff(original, tmp_path / "portable")
    science.unlink()
    original.unlink()
    assert verify_handoff(packaged)["ready_for_grid_import"] is True
    assert (tmp_path / "portable" / "science_bundle.json").is_file()


def test_pack_handoff_refuses_to_overwrite_existing_directory(tmp_path):
    import pytest
    science = tmp_path / "science.json"
    science.write_text('{"x":1}', encoding="utf-8")
    original = tmp_path / "source-handoff.json"
    write_handoff(original, science)
    target = tmp_path / "portable"
    target.mkdir()
    (target / "keep.txt").write_text("safe", encoding="utf-8")
    with pytest.raises(FileExistsError):
        pack_handoff(original, target)
    assert (target / "keep.txt").read_text(encoding="utf-8") == "safe"
