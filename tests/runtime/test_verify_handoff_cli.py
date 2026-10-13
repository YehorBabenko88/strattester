import json
from strattester.runtime.verify_handoff_cli import main
from strattester.runtime.grid_handoff import write_handoff


def test_verify_handoff_cli_success(tmp_path, capsys):
    science = tmp_path / "science.json"
    science.write_text('{"symbols":[]}', encoding="utf-8")
    manifest = tmp_path / "handoff.json"
    write_handoff(manifest, science)
    assert main([str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_verify_handoff_cli_fails_on_corruption(tmp_path, capsys):
    science = tmp_path / "science.json"
    science.write_text('{"symbols":[]}', encoding="utf-8")
    manifest = tmp_path / "handoff.json"
    write_handoff(manifest, science)
    science.write_text('{"symbols":[1]}', encoding="utf-8")
    assert main([str(manifest)]) == 2
    assert json.loads(capsys.readouterr().err)["ok"] is False


def test_verify_handoff_cli_pack_and_verify(tmp_path, capsys):
    science = tmp_path / "science.json"
    science.write_text('{"symbols":[]}', encoding="utf-8")
    source = tmp_path / "source-handoff.json"
    write_handoff(source, science)
    dest = tmp_path / "portable"
    assert main([str(source), "--pack", str(dest)]) == 0
    assert json.loads(capsys.readouterr().out)["manifest"] == str(dest / "grid-handoff.json")
    science.unlink()
    assert main([str(dest / "grid-handoff.json")]) == 0


def test_verify_handoff_cli_pack_refuses_existing_target(tmp_path, capsys):
    science = tmp_path / "science.json"
    science.write_text('{"symbols":[]}', encoding="utf-8")
    source = tmp_path / "source-handoff.json"
    write_handoff(source, science)
    target = tmp_path / "existing"
    target.mkdir()
    assert main([str(source), "--pack", str(target)]) == 2
    assert json.loads(capsys.readouterr().err)["ok"] is False
