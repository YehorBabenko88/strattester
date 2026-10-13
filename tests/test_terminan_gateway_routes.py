import importlib
import io
import json


def request(path):
    gateway = importlib.import_module('strattester.terminan_gateway')
    handler = object.__new__(gateway.Handler)
    handler.path = path
    handler.wfile = io.BytesIO()
    status = []
    handler.send_response = status.append
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    handler.do_GET()
    return status[0], json.loads(handler.wfile.getvalue())


def test_runs_endpoint_without_source_is_readonly(monkeypatch):
    monkeypatch.delenv('TERMINAN_RESULTS_DB', raising=False)
    status, body = request('/v1/runs?symbol=BTCUSDT')
    assert status == 200
    assert body == {'version': 1, 'symbol': 'BTCUSDT', 'state': 'SOURCE_UNAVAILABLE', 'runs': []}


def test_trades_endpoint_without_source_is_readonly(monkeypatch):
    monkeypatch.delenv('TERMINAN_RESULTS_DB', raising=False)
    status, body = request('/v1/trades?symbol=BTCUSDT&run_id=r1')
    assert status == 200
    assert body == {'version': 1, 'symbol': 'BTCUSDT', 'run_id': 'r1', 'state': 'SOURCE_UNAVAILABLE', 'trades': []}


def test_trades_rejects_missing_run_id(monkeypatch):
    monkeypatch.delenv('TERMINAN_RESULTS_DB', raising=False)
    status, body = request('/v1/trades?symbol=BTCUSDT')
    assert status == 400
    assert body == {'error': 'invalid run ID'}


def test_runs_and_trades_read_sqlite_fixture_without_writes(tmp_path, monkeypatch):
    import sqlite3
    from strattester.terminan_trade_journal import append_trades
    db = tmp_path / 'results.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE research_results (run_id, strategy_id, strategy_version, created_at, metrics, job_id, lease_token, node_generation, symbol)')
        con.execute('INSERT INTO research_results VALUES (?,?,?,?,?,?,?,?,?)', ('r1', 's1', 'v1', 1000, '{"net_pnl": 9}', 'j1', 'lease1', 1, 'BTCUSDT'))
        append_trades(con, 'r1', 'BTCUSDT', 's1', [dict(entry_time=1000, exit_time=2000, entry_price=100, exit_price=110, side='long', quantity=1, net_pnl=9, fees=1, metadata={})])
    before = db.read_bytes()
    monkeypatch.setenv('TERMINAN_RESULTS_DB', str(db))
    status, body = request('/v1/runs?symbol=BTCUSDT')
    assert status == 200
    assert body['runs'] == [dict(run_id='r1', strategy_id='s1', strategy_version='v1', created_at=1000, metrics={'net_pnl': 9}, fenced=True)]
    status, body = request('/v1/trades?symbol=BTCUSDT&run_id=r1')
    assert status == 200
    assert len(body['trades']) == 1
    assert body['trades'][0]['entry_ms'] == 1000
    assert body['trades'][0]['net_pnl'] == 9
    assert db.read_bytes() == before


def test_runs_zero_generation_is_fenced_and_readonly(tmp_path, monkeypatch):
    import sqlite3
    db = tmp_path / 'results.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE research_results (run_id, strategy_id, strategy_version, created_at, metrics, job_id, lease_token, node_generation, symbol)')
        con.execute('INSERT INTO research_results VALUES (?,?,?,?,?,?,?,?,?)', ('r0', 's1', 'v1', 1000, '{}', 'j0', 'lease0', 0, 'BTCUSDT'))
        con.execute('INSERT INTO research_results VALUES (?,?,?,?,?,?,?,?,?)', ('r1', 's1', 'v1', 1001, '{}', 'j1', None, 1, 'BTCUSDT'))
        con.execute('INSERT INTO research_results VALUES (?,?,?,?,?,?,?,?,?)', ('r2', 's1', 'v1', 1002, '{}', '', 'lease2', 2, 'BTCUSDT'))
        con.execute('INSERT INTO research_results VALUES (?,?,?,?,?,?,?,?,?)', ('r3', 's1', 'v1', 1003, '{}', 'j3', '', 3, 'BTCUSDT'))
    before = db.read_bytes()
    monkeypatch.setenv('TERMINAN_RESULTS_DB', str(db))
    status, body = request('/v1/runs?symbol=BTCUSDT')
    assert status == 200
    by_id = {row['run_id']: row for row in body['runs']}
    assert by_id['r0']['fenced'] is True
    assert by_id['r1']['fenced'] is False
    assert by_id['r2']['fenced'] is False
    assert by_id['r3']['fenced'] is False
    assert db.read_bytes() == before


def test_runs_rejects_invalid_limits_even_without_source(monkeypatch):
    monkeypatch.delenv('TERMINAN_RESULTS_DB', raising=False)
    for limit in ('0', '-1', '501', 'not-a-number'):
        status, body = request('/v1/runs?symbol=BTCUSDT&limit=' + limit)
        assert status == 400
        assert 'error' in body


def test_runs_accepts_valid_limit_without_source(monkeypatch):
    monkeypatch.delenv('TERMINAN_RESULTS_DB', raising=False)
    status, body = request('/v1/runs?symbol=BTCUSDT&limit=500')
    assert status == 200
    assert body['state'] == 'SOURCE_UNAVAILABLE'
