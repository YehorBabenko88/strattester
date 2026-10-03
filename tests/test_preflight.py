from strattester.preflight import run_preflight

def test_preflight_is_non_destructive_and_reports_core_checks(tmp_path):
    report=run_preflight(tmp_path,check_network=False)
    names={x.name:x for x in report.checks}
    assert names['python'].ok
    assert names['directories'].ok
    assert names['sqlite_state'].ok
    assert names['package_import'].ok
    assert 'market_db' in names and 'telegram' in names and 'tailscale' in names
    assert not (tmp_path/'data'/'bybit_1m.sqlite3').exists()

def test_preflight_required_ok_ignores_optional_remote_configuration(tmp_path):
    report=run_preflight(tmp_path,check_network=False)
    assert report.required_ok
