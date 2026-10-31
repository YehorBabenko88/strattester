"""Producer-owned records: positive compatibility and fail-closed admission."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import types

import pytest
from strattester.engine.executor import ResearchExecutionPermit
from strattester.marketdata.sqlite_store import Candle, SQLiteMarketStore
from strattester.persistence.result_store import ResultStore
from strattester.readonly_api import ReadOnlyResultsApp
from strattester.research.runner import ResearchRunner
from strattester.strategies.base import DataRequirement, StrategyDefinition


class SumStrategy:
    def run(self, candles, checkpoint=None):
        return {'sum': sum(c.close for c in candles)}


DEFINITION = StrategyDefinition('receipt-sum', '1', (DataRequirement('candles', ('1m',)),), SumStrategy)
META = dict(source_identity='synthetic:fixture', market_type='linear', producer_identity='synthetic:owner',
            source_revision='a' * 40, model={'kind': 'synthetic', 'version': '1'},
            execution_assumptions={'fees': 0, 'slippage': 0, 'execution': 'none'})


@pytest.fixture
def sources(tmp_path):
    market = SQLiteMarketStore.open(tmp_path / 'market.db')
    market.upsert_candles([Candle('BTCUSDT', '1m', t, 1, 2, 1, 2, 1) for t in (0, 60000)])
    results = ResultStore.open(tmp_path / 'results.db')
    runner = ResearchRunner(market, object(), clock_ms=lambda: 999999)
    yield market, results, runner
    results.close()
    market.close()


def produce(sources, definition=DEFINITION, **kwargs):
    _, results, runner = sources
    runner.run(definition, {'symbol': 'BTCUSDT', 'launchTime': '0'}, start_ms=0, end_ms=60000,
               result_store=results, provenance=META, **kwargs)
    return json.loads(results.con.execute("SELECT record FROM owned_runs WHERE state='COMPLETE'").fetchone()[0])


def request(results, record, *, receipt=None):
    app = ReadOnlyResultsApp(results.path,
        trusted_sources=[(record['producer_identity'], record['source_revision'], record['dataset']['source_identity'])],
        trusted_receipts=[(record['producer_identity'], record['source_revision'], record['run_id'], receipt or record['completion_receipt'])])
    statuses = []
    body = b''.join(app({'PATH_INFO': '/internal/v1/runs', 'REQUEST_METHOD': 'GET'},
                        lambda status, headers: statuses.append(status)))
    return statuses[0], json.loads(body)


def test_runner_seals_real_input_and_api_serves_owner_admitted_record(sources):
    _, results, _ = sources
    record = produce(sources)
    assert record['metrics'] == {'sum': 4}
    assert record['input_snapshot'][0]['rows'][0]['open_time'] == 0
    assert record['dataset']['coverage'] == 'COMPLETE'
    assert record['execution_authority'] is False
    status, body = request(results, record)
    assert status == '200 OK'
    assert body['runs'] == [record]
    assert body['source_authenticity'] == 'OWNER_POLICY_ADMITTED'
    with pytest.raises(sqlite3.IntegrityError):
        results.con.execute("UPDATE owned_runs SET record='{}'")
    results.con.rollback()


def test_actual_grid_handoff_accepts_only_exact_owner_receipt(sources):
    record = produce(sources)
    grid = Path('/workspace/bybit-cluster-grid/grid')
    if not grid.exists():
        pytest.skip('cross-repository Grid contract checkout unavailable')
    package = types.ModuleType('_receipt_grid_contract')
    package.__path__ = [str(grid)]
    sys.modules[package.__name__] = package
    spec = importlib.util.spec_from_file_location(package.__name__ + '.research_handoff', grid / 'research_handoff.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy = {(record['producer_identity'], record['source_revision'], record['run_id'], record['completion_receipt'])}
    assert module.accept_handoff(record, policy)['status'] == 'ACCEPTED_HISTORICAL'
    assert module.accept_handoff(record, policy)['trading_authorized'] is False
    assert module.accept_handoff(record, set())['status'] == 'UNAVAILABLE'


def test_wrong_receipt_policy_does_not_admit_owned_record(sources):
    _, results, _ = sources
    record = produce(sources)
    status, body = request(results, record, receipt='0' * 64)
    assert status == '503 Service Unavailable'
    assert body['reason'] == 'SOURCE_RECEIPT_UNTRUSTED'
    assert 'runs' not in body


def test_tampered_record_is_rejected_even_if_owner_pins_original_receipt(sources):
    from strattester.research.provenance import validate
    record = produce(sources)
    record['metrics']['sum'] = 999
    assert validate(record) == 'RECEIPT_INVALID'


def test_owned_runner_cannot_bypass_disabled_strategy_permission(sources):
    _, results, runner = sources
    disabled = StrategyDefinition('disabled', '1', DEFINITION.requirements, SumStrategy, enabled=False)
    with pytest.raises(ValueError, match='permission'):
        produce(sources, disabled)
    assert results.con.execute('SELECT count(*) FROM owned_runs').fetchone()[0] == 0
    permit = ResearchExecutionPermit.for_strategy(disabled, reason='disposable receipt test')
    assert produce(sources, disabled, research_permission=permit)['metrics'] == {'sum': 4}


def test_owned_direct_executor_also_requires_permission(sources):
    from strattester.research.provenance import execute_owned
    market, results, _ = sources
    disabled = StrategyDefinition('disabled', '1', DEFINITION.requirements, SumStrategy, enabled=False)
    with pytest.raises(ValueError, match='permission'):
        execute_owned(disabled, market, 'BTCUSDT', 0, 60000, results, **META)
    assert results.con.execute('SELECT count(*) FROM owned_runs').fetchone()[0] == 0


def test_lease_loss_prevents_completion(sources):
    _, results, _ = sources
    with pytest.raises(RuntimeError, match='PUBLICATION_FENCED'):
        produce(sources, lease_validator=lambda: False)
    assert results.con.execute("SELECT count(*) FROM owned_runs WHERE state='COMPLETE'").fetchone()[0] == 0


def test_rehashed_invalid_row_is_not_a_valid_record(sources):
    from strattester.research.provenance import digest, validate
    record = copy.deepcopy(produce(sources))
    record['input_snapshot'][0]['rows'][0]['close'] = True
    record['dataset']['fingerprint'] = digest(dict(dataset={k: v for k, v in record['dataset'].items() if k != 'fingerprint'}, rows=record['input_snapshot']))
    record['completion_receipt'] = digest({k: v for k, v in record.items() if k != 'completion_receipt'})
    assert validate(record) == 'DATA_QUALITY_INVALID'


@pytest.mark.parametrize('dataset', ['public_trades', 'invented_dataset'])
def test_rehashed_unsupported_or_invalid_aggregate_rows_are_rejected(sources, dataset):
    from strattester.research.provenance import digest, validate
    record = produce(sources)
    entry = record['input_snapshot'][0]
    entry['dataset'] = dataset
    record['dataset']['datasets'][0]['dataset'] = dataset
    for row in entry['rows']:
        row.update(buy_volume=-9, sell_volume=True, turnover=-1, trade_count=-10)
    record['dataset']['fingerprint'] = digest(dict(
        dataset={k: v for k, v in record['dataset'].items() if k != 'fingerprint'},
        rows=record['input_snapshot']))
    record['completion_receipt'] = digest({k: v for k, v in record.items() if k != 'completion_receipt'})
    assert validate(record) == 'DATA_QUALITY_INVALID'
