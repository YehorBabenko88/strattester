import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install.ps1"
SERVICE_INSTALLER = REPO / "service" / "install_windows.ps1"


def _powershell():
    exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if not exe:
        pytest.skip("Windows PowerShell is not available")
    return exe


@pytest.mark.skipif(os.name != "nt", reason="Windows installer test")
def test_dry_run_from_foreign_cwd_is_side_effect_free(tmp_path):
    powershell = _powershell()

    foreign_cwd = tmp_path / "foreign"
    target = tmp_path / "target"

    foreign_cwd.mkdir()

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
            "-InstallDir",
            str(target),
            "-PythonExe",
            sys.executable,
            "-DryRun",
        ],
        cwd=foreign_cwd,
        text=True,
        capture_output=True,
        timeout=60,
    )

    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Strattester source import: OK" in output
    assert "Dry-run validation passed" in output
    assert not target.exists()


def _write_fake_nssm(tmp_path: Path):
    fake_ps1 = tmp_path / "fake-nssm.ps1"
    fake_cmd = tmp_path / "fake-nssm.cmd"
    log_file = tmp_path / "nssm-calls.log"

    fake_ps1.write_text(
        r'''
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$NssmArgs
)

$LogFile = $env:FAKE_NSSM_LOG
$FailOn  = $env:FAKE_NSSM_FAIL_ON

$Line = ($NssmArgs -join "|")
Add-Content -LiteralPath $LogFile -Value $Line -Encoding UTF8

$Command = if($NssmArgs.Count -gt 0){
    $NssmArgs[0]
}
else {
    ""
}

if($Command -eq "stop" -or $Command -eq "remove"){
    exit 3
}

if($FailOn -and $Command -eq $FailOn){
    switch($Command){
        "install" { exit 7 }
        "set"     { exit 8 }
        "start"   { exit 9 }
        default   { exit 10 }
    }
}

exit 0
'''.lstrip(),
        encoding="utf-8",
    )

    fake_cmd.write_text(
        '@echo off\r\n'
        f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{fake_ps1}" %*\r\n'
        'exit /b %ERRORLEVEL%\r\n',
        encoding="ascii",
    )

    return fake_cmd, log_file


def _prepare_fake_install(tmp_path: Path):
    install_dir = tmp_path / "install"
    scripts_dir = install_dir / ".venv" / "Scripts"
    logs_dir = install_dir / "logs"

    scripts_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    # The installer only validates existence of runtime Python.
    (scripts_dir / "python.exe").write_bytes(b"")

    return install_dir


@pytest.mark.skipif(os.name != "nt", reason="Windows NSSM test")
@pytest.mark.parametrize(
    ("fail_on", "required", "forbidden"),
    [
        (
            "install",
            "install|StrattesterGuardian",
            "set|StrattesterGuardian",
        ),
        (
            "set",
            "set|StrattesterGuardian",
            "start|StrattesterWorker",
        ),
        (
            "start",
            "start|StrattesterWorker",
            "start|StrattesterGuardian",
        ),
    ],
)
def test_service_installer_is_fail_closed(
    tmp_path,
    fail_on,
    required,
    forbidden,
):
    powershell = _powershell()

    fake_nssm, log_file = _write_fake_nssm(tmp_path)
    install_dir = _prepare_fake_install(tmp_path)

    env = os.environ.copy()
    env["FAKE_NSSM_LOG"] = str(log_file)
    env["FAKE_NSSM_FAIL_ON"] = fail_on

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SERVICE_INSTALLER),
            "-InstallDir",
            str(install_dir),
            "-NssmExe",
            str(fake_nssm),
            "-Role",
            "Worker",
        ],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode != 0

    assert log_file.exists()

    calls = log_file.read_text(
        encoding="utf-8-sig",
        errors="replace",
    ).splitlines()

    assert any(required in line for line in calls), calls
    assert not any(forbidden in line for line in calls), calls


@pytest.mark.skipif(os.name != "nt", reason="Windows NSSM test")
def test_nssm_cleanup_failures_are_tolerated(tmp_path):
    powershell = _powershell()

    fake_nssm, log_file = _write_fake_nssm(tmp_path)
    install_dir = _prepare_fake_install(tmp_path)

    env = os.environ.copy()
    env["FAKE_NSSM_LOG"] = str(log_file)
    env.pop("FAKE_NSSM_FAIL_ON", None)

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SERVICE_INSTALLER),
            "-InstallDir",
            str(install_dir),
            "-NssmExe",
            str(fake_nssm),
            "-Role",
            "Worker",
        ],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    output = result.stdout + result.stderr

    assert result.returncode == 0, output

    calls = log_file.read_text(
        encoding="utf-8-sig",
        errors="replace",
    ).splitlines()

    assert any(
        "stop|StrattesterGuardian|confirm" in line
        for line in calls
    )
    assert any(
        "remove|StrattesterGuardian|confirm" in line
        for line in calls
    )
    assert any(
        "start|StrattesterWorker" in line
        for line in calls
    )
    assert any(
        "start|StrattesterGuardian" in line
        for line in calls
    )
