from pathlib import Path
import json
import subprocess
import sys
def test_install_script_preserves_external_runtime_directories():
    text=Path('install.ps1').read_text(encoding='utf-8')
    for name in ('data','state','results','logs','releases'): assert f'"{name}"' in text
    assert 'Remove-Item' not in text
def test_uninstall_requires_explicit_delete_confirmation():
    text=Path('service/uninstall_windows.ps1').read_text(encoding='utf-8')
    assert 'DeleteData' in text and 'DELETE-DATA' in text
def test_install_has_dry_run():
    assert 'DryRun' in Path('install.ps1').read_text(encoding='utf-8')


def test_legacy_installer_runs_preflight_without_starting_workers():
    script = Path('install.ps1').read_text(encoding='utf-8')
    assert '-m strattester.preflight_cli' in script
    assert 'strattester.smoke_cli' not in script
    assert 'download_smoke_cli' not in script
    assert '--network' not in script


def test_legacy_installer_leaves_service_registration_to_unified():
    script = Path('install.ps1').read_text(encoding='utf-8')
    assert 'service\\install_windows.ps1' not in script
    assert script.index('UNIFIED_SERVICE_INSTALL_REQUIRED') < script.index('New-Item')


def test_explicit_smoke_uses_and_removes_disposable_state(tmp_path):
    original_state = tmp_path / 'state'
    original_state.mkdir()
    marker = original_state / 'smoke_state.sqlite3'
    marker.write_bytes(b'preserve existing state')
    result = subprocess.run(
        [sys.executable, '-m', 'strattester.smoke_cli', '--root', str(tmp_path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    assert json.loads(result.stdout)['reopened_state'] == 'COMPLETE'
    assert list(tmp_path.iterdir()) == [original_state]
    assert marker.read_bytes() == b'preserve existing state'
