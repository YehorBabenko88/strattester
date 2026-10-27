import json

from strattester.persistence.result_store import ResultStore


def request(path, method='GET', query='', source=None):
    from strattester.readonly_api import ReadOnlyResultsApp
    captured = []
    body = b''.join(ReadOnlyResultsApp(source)({'PATH_INFO': path, 'REQUEST_METHOD': method,
        'QUERY_STRING': query}, lambda status, headers: captured.append((status, headers))))
    return int(captured[0][0].split()[0]), json.loads(body)


def test_capabilities_never_advertise_unqualified_results():
    status, data = request('/internal/v1/capabilities')
    assert status == 200
    assert data['api_version'] == {'major': 1, 'minor': 0}
    assert data['capabilities'] == {'historical_research': False, 'runs': False, 'run_metrics': False, 'immutable_research_v1_1': True}
    assert data['read_only'] is True


def test_source_results_are_mutable_and_lack_dataset_identity(tmp_path):
    path = tmp_path / 'results.sqlite'
    store = ResultStore.open(path)
    store.put('run', 'BTCUSDT', 'strategy', '1', {'fingerprint': 'strategy-only', 'net_pnl': 1}, 1.25)
    store.put('run', 'BTCUSDT', 'strategy', '1', {'fingerprint': 'strategy-only', 'net_pnl': 2}, 2.25)
    assert store.latest('BTCUSDT', 'strategy')['metrics']['net_pnl'] == 2
    assert 'dataset_fingerprint' not in {r[1] for r in store.con.execute('PRAGMA table_info(research_results)')}
    store.close()
    before = path.read_bytes()
    for route in ('/health', '/runs', '/runs/run/metrics'):
        status, data = request('/internal/v1' + route, source=path)
        assert status == 503
        assert data['reason'] == ('SOURCE_PROVENANCE_UNQUALIFIED' if route == '/health' else 'SOURCE_TRUST_UNCONFIGURED')
        assert 'metrics' not in data and 'run_id' not in data
    assert path.read_bytes() == before


def test_missing_source_is_not_created(tmp_path):
    path = tmp_path / 'missing.sqlite'
    status, data = request('/internal/v1/health', source=path)
    assert status == 503 and data['reason'] == 'SOURCE_UNAVAILABLE'
    assert not path.exists()


def test_reject_writes_unknown_routes_and_unbounded_queries():
    assert request('/internal/v1/runs', 'POST')[0] == 405
    assert request('/internal/v2/runs')[0] == 404
    for query in ('limit=0', 'limit=101', 'limit=true', 'offset=-1', 'limit=1&limit=2', 'secret=value'):
        assert request('/internal/v1/runs', query=query)[0] == 400
    assert request('/internal/v1/runs', query='limit=100&offset=0')[0] == 503
