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

def test_dry_run_is_before_all_install_mutations():
    text = Path('install.ps1').read_text(encoding='utf-8')

    dry_run = text.index('if($DryRun){')
    first_mutation = text.index('New-Item -ItemType Directory')

    assert dry_run < first_mutation


def test_dry_run_does_not_call_mutating_preflight():
    text = Path('install.ps1').read_text(encoding='utf-8')

    start = text.index('if($DryRun){')
    end = text.index('New-Item -ItemType Directory')
    dry_run_block = text[start:end]

    assert 'strattester.preflight_cli' not in dry_run_block
    assert 'New-Item' not in dry_run_block
    assert 'Remove-Item' not in dry_run_block
    assert 'pip install' not in dry_run_block
    assert 'strattester_state.sqlite3' not in dry_run_block


def test_dry_run_exits_before_installation():
    text = Path('install.ps1').read_text(encoding='utf-8')

    start = text.index('if($DryRun){')
    end = text.index('New-Item -ItemType Directory')
    dry_run_block = text[start:end]

    assert 'exit 0' in dry_run_block
