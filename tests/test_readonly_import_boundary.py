"""Independent fixture-only admission tests for the selective import."""
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def call(path, source, method='GET', query=''):
    from strattester.readonly_api import ReadOnlyResultsApp
    response = []
    body = b''.join(ReadOnlyResultsApp(source)(
        {'PATH_INFO': path, 'REQUEST_METHOD': method, 'QUERY_STRING': query},
        lambda status, headers: response.append((status, dict(headers)))))
    return int(response[0][0].split()[0]), response[0][1], json.loads(body)


@pytest.mark.parametrize('state', ['COMPLETE', 'RUNNING', 'ABORTED', 'FAILED', 'CANCELLED'])
@pytest.mark.parametrize('alteration', ['original', 'tampered', 'self_rehashed', 'other_source'])
def test_no_admission_from_caller_owned_receipts(tmp_path, state, alteration):
    source = tmp_path / 'fixture.sqlite'
    record = {'run_id': 'forged', 'producer_identity': 'caller',
              'source_revision': 'a' * 40, 'dataset': {'source_identity': 'fixture'},
              'metrics': {'secret': 'must-not-be-exposed'}, 'execution_authority': False}
    record['completion_receipt'] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    if alteration in ('tampered', 'self_rehashed'):
        record['metrics']['secret'] = 'altered-secret'
    if alteration == 'other_source':
        record['dataset']['source_identity'] = 'other-source'
    if alteration == 'self_rehashed':
        record['completion_receipt'] = hashlib.sha256(json.dumps(
            {k: v for k, v in record.items() if k != 'completion_receipt'}, sort_keys=True).encode()).hexdigest()
    with sqlite3.connect(source) as con:
        con.execute('CREATE TABLE research_results(metrics TEXT)')
        con.execute('CREATE TABLE owned_runs(run_id TEXT, state TEXT, record TEXT)')
        con.execute('INSERT INTO owned_runs VALUES(?,?,?)', ('forged', state, json.dumps(record)))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    for route in ('health', 'runs', 'runs/forged/metrics'):
        status, headers, body = call('/internal/v1/' + route, source)
        assert status == 503
        assert body['reason'] == 'SOURCE_PROVENANCE_UNQUALIFIED'
        assert body['provenance'] == 'UNAVAILABLE'
        assert not {'runs', 'metrics', 'execution_authority', 'run_id'} & body.keys()
        assert headers['Cache-Control'] == 'no-store'
        assert headers['Content-Type'] == 'application/json'
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_missing_parent_and_source_are_never_created(tmp_path):
    source = tmp_path / 'absent-directory' / 'missing.sqlite'
    for route in ('health', 'runs', 'runs/no-such-run/metrics'):
        status, _, data = call('/internal/v1/' + route, source)
        assert (status, data['reason']) == (503, 'SOURCE_UNAVAILABLE')
    assert list(tmp_path.iterdir()) == []


def test_routes_and_capabilities_are_bounded_and_read_only(tmp_path):
    source = tmp_path / 'missing.sqlite'
    status, _, body = call('/internal/v1/capabilities', source)
    assert status == 200
    assert not any(body['capabilities'].values())
    for method in ('POST', 'PUT', 'DELETE', 'PATCH', 'HEAD'):
        status, headers, _ = call('/internal/v1/runs', source, method)
        assert status == 405 and headers['Allow'] == 'GET'
    for query in ('limit=101', 'offset=10001', 'limit=1&limit=2', 'x=1', 'x' * 257):
        assert call('/internal/v1/runs', source, query=query)[0] == 400
    assert call('/internal/v1/runs/../../metrics', source)[0] == 404
    assert not source.exists()


@pytest.mark.parametrize('source', [r'\\server\share\file.sqlite', '//server/share/file.sqlite',
    r'\/server/share/file.sqlite', r'\\?\C:\fixture.sqlite', r'\\.\NUL',
    r'C:\fixture.sqlite:stream', r'C:\one\..\fixture.sqlite', r'C:\NUL', 'relative.sqlite'])
def test_invalid_sources_rejected_before_filesystem_or_sqlite(source):
    # These strings are never passed to the OS. In particular no UNC is probed.
    with patch.object(Path, 'resolve', side_effect=AssertionError('resolve IO')), \
         patch.object(Path, 'lstat', side_effect=AssertionError('lstat IO')), \
         patch('sqlite3.connect', side_effect=AssertionError('database IO')):
        status, _, data = call('/internal/v1/health', source)
    assert (status, data['reason']) == (503, 'SOURCE_UNAVAILABLE')
    assert source not in json.dumps(data)


def test_constructor_performs_no_filesystem_or_socket_io(tmp_path):
    from strattester.readonly_api import ReadOnlyResultsApp
    with patch.object(Path, 'resolve', side_effect=AssertionError('resolve IO')), \
         patch.object(Path, 'lstat', side_effect=AssertionError('lstat IO')), \
         patch('socket.socket', side_effect=AssertionError('socket IO')):
        ReadOnlyResultsApp(tmp_path / 'fixture.sqlite')
        assert call('/internal/v1/health', None)[0] == 503


@pytest.mark.parametrize('kind', ['ancestor_reparse', 'hardlink', 'directory'])
def test_linked_and_nonordinary_sources_blocked_before_sqlite(tmp_path, kind):
    import stat
    source = tmp_path / 'fixture.sqlite'
    source.write_bytes(b'fixture')
    original = Path.lstat
    def metadata(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if (kind == 'ancestor_reparse' and path == tmp_path) or (kind != 'ancestor_reparse' and path == source):
            return SimpleNamespace(st_mode=stat.S_IFDIR if kind == 'directory' else stat.S_IFREG,
                st_file_attributes=0x400 if kind == 'ancestor_reparse' else 0,
                st_nlink=2 if kind == 'hardlink' else 1)
        return info
    with patch.object(Path, 'lstat', metadata), \
         patch('sqlite3.connect', side_effect=AssertionError('database IO')):
        status, _, data = call('/internal/v1/health', source)
    assert (status, data['reason']) == (503, 'SOURCE_UNAVAILABLE')
