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
