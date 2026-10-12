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
