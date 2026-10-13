"""Smoke-test the machine-readable doctor CLI without touching a real cluster."""
import json

from strattester import doctor_cli


def test_doctor_cli_reports_all_diagnostics(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor_cli.AppConfig, "load", lambda root: root)
    from strattester.doctor import DoctorReport
    monkeypatch.setattr(doctor_cli, "run_doctor", lambda config: DoctorReport(
        python_supported=True, paths_writable=True, market_db_exists=False,
        free_disk_bytes=123, postgres_configured=False, tailscale_available=False))
    assert doctor_cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["free_disk_bytes"] == 123
    assert payload["market_db_exists"] is False


def test_doctor_cli_fails_closed_on_unwritable_paths(monkeypatch, capsys, tmp_path):
    from strattester.doctor import DoctorReport
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor_cli.AppConfig, "load", lambda root: root)
    monkeypatch.setattr(doctor_cli, "run_doctor", lambda config: DoctorReport(
        python_supported=True, paths_writable=False, market_db_exists=False,
        free_disk_bytes=0, postgres_configured=False, tailscale_available=False))
    assert doctor_cli.main() == 2
    assert json.loads(capsys.readouterr().out)["paths_writable"] is False
