from pathlib import Path


SERVICE_INSTALLER = Path("service/install_windows.ps1")


def _text() -> str:
    return SERVICE_INSTALLER.read_text(encoding="utf-8")


def test_service_installer_has_strict_nssm_wrapper():
    text = _text()

    assert "function Invoke-NssmStrict" in text
    assert "if($LASTEXITCODE -ne 0)" in text
    assert "throw" in text


def test_service_installer_has_best_effort_cleanup_wrapper():
    text = _text()

    assert "function Invoke-NssmBestEffort" in text
    assert "function Remove-ServiceIfPresent" in text

    assert 'Invoke-NssmBestEffort @("stop",$Name,"confirm")' in text
    assert 'Invoke-NssmBestEffort @("remove",$Name,"confirm")' in text


def test_service_install_is_strict():
    text = _text()

    marker = '@("install",$Name,$py,"-m $Module")'
    pos = text.index(marker)

    prefix = text[max(0, pos - 250):pos]

    assert "Invoke-NssmStrict" in prefix


def test_service_configuration_is_strict():
    text = _text()

    settings = (
        "AppDirectory",
        "ObjectName",
        "SERVICE_AUTO_START",
        "AppExit",
        "AppRestartDelay",
        "AppThrottle",
        "AppKillProcessTree",
        "AppStdout",
        "AppStderr",
        "AppRotateFiles",
        "AppRotateBytes",
    )

    for setting in settings:
        pos = text.index(setting)
        prefix = text[max(0, pos - 300):pos]
        assert "Invoke-NssmStrict" in prefix, setting


def test_service_start_is_strict():
    text = _text()

    for service in (
        "StrattesterController",
        "StrattesterWorker",
        "StrattesterGuardian",
    ):
        marker = f'@("start","{service}")'
        pos = text.index(marker)

        prefix = text[max(0, pos - 250):pos]

        assert "Invoke-NssmStrict" in prefix, service


def test_observer_removes_active_execution_services():
    text = _text()

    start = text.index('if($Role -eq "Observer"){')
    end = text.index("Install-ServiceSafe", start)
    block = text[start:end]

    assert 'Remove-ServiceIfPresent "StrattesterWorker"' in block
    assert 'Remove-ServiceIfPresent "StrattesterGuardian"' in block
    assert "exit 0" in block


def test_nssm_executable_is_validated():
    text = _text()

    assert "Test-Path $NssmExe" in text
    assert "NSSM executable not found" in text


def test_runtime_python_is_validated_before_service_changes():
    text = _text()

    python_check = text.index("Runtime Python not found")
    first_service_change = text.index("function Invoke-NssmStrict")

    assert python_check < first_service_change
