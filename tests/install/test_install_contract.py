from pathlib import Path
def test_install_script_preserves_external_runtime_directories():
    text=Path('install.ps1').read_text(encoding='utf-8')
    for name in ('data','state','results','logs','releases'): assert f'"{name}"' in text
    assert 'Remove-Item' not in text
def test_uninstall_requires_explicit_delete_confirmation():
    text=Path('service/uninstall_windows.ps1').read_text(encoding='utf-8')
    assert 'DeleteData' in text and 'DELETE-DATA' in text
def test_install_has_dry_run():
    assert 'DryRun' in Path('install.ps1').read_text(encoding='utf-8')


def test_legacy_installer_starts_only_offline_smoke_checks():
    script = Path('install.ps1').read_text(encoding='utf-8')
    assert '-m strattester.smoke_cli' in script
    assert 'download_smoke_cli' not in script
    assert '--network' not in script


def test_legacy_installer_leaves_service_registration_to_unified():
    script = Path('install.ps1').read_text(encoding='utf-8')
    assert 'service\\install_windows.ps1' not in script
    assert script.index('UNIFIED_SERVICE_INSTALL_REQUIRED') < script.index('New-Item')
