from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import DataRequirement, SyncEngine, SyncState

HOUR = 3_600_000


class FundingClient:
    def __init__(self, events):
        self.events = events
        self.calls = []

    def fetch_funding(self, symbol, start, end):
        self.calls.append((start, end))
        return [
            {'fundingRateTimestamp': str(ts), 'fundingRate': '0.0001'}
            for ts in sorted(self.events, reverse=True)
            if start <= ts <= end
        ]


def test_verified_eight_hour_funding_ready_and_idempotent(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0, 8 * HOUR, 16 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    req = DataRequirement('BTCUSDT', 'funding', '1m', 0, 16 * HOUR)
    assert engine.sync_requirement(req).state is SyncState.READY
    assert store.coverage('BTCUSDT', 'funding').count == 3
    assert engine.sync_requirement(req).state is SyncState.READY
    store.close()


def test_missing_funding_event_remains_partial(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0, 16 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 16 * HOUR)
    )
    assert result.state is SyncState.PARTIAL
    store.close()


def test_funding_schedule_with_offset_anchor(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([HOUR, 9 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'X': (8 * HOUR, HOUR)},
    )
    assert engine.sync_requirement(
        DataRequirement('X', 'funding', '5m', 0, 10 * HOUR)
    ).state is SyncState.READY
    assert client.calls == [(HOUR, 9 * HOUR)]
    store.close()


def test_unverified_schedule_fails_closed_without_network(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0])
    engine = SyncEngine(store, client)
    result = engine.sync_requirement(DataRequirement('X', 'funding', '480m', 0, 0))
    assert result.state is SyncState.UNAVAILABLE
    assert client.calls == []
    store.close()


def test_future_funding_event_never_claims_ready_or_calls_exchange(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0, 8 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 4 * HOUR,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 8 * HOUR)
    )
    assert result.state is SyncState.PARTIAL
    assert 'future' in result.message
    assert client.calls == []
    store.close()


def test_future_funding_cached_row_does_not_bypass_gate(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    store.upsert_funding('BTCUSDT', [
        {'fundingRateTimestamp': '0', 'fundingRate': '0.001'},
        {'fundingRateTimestamp': str(8 * HOUR), 'fundingRate': '0.001'},
    ])
    client = FundingClient([])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 4 * HOUR,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 8 * HOUR)
    )
    assert result.state is SyncState.PARTIAL
    assert client.calls == []
    store.close()


def test_off_schedule_funding_page_is_rejected_without_partial_write(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0, 4 * HOUR, 8 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 8 * HOUR)
    )
    assert result.state is SyncState.RETRYABLE
    assert store.coverage('BTCUSDT', 'funding').count == 0
    store.close()


def test_duplicate_funding_page_is_rejected_without_write(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Duplicates:
        def fetch_funding(self, symbol, start, end):
            return [
                {'fundingRateTimestamp': '0', 'fundingRate': '0.0001'},
                {'fundingRateTimestamp': '0', 'fundingRate': '0.0002'},
            ]
    engine = SyncEngine(
        store, Duplicates(), clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 0)
    )
    assert result.state is SyncState.RETRYABLE
    assert store.coverage('BTCUSDT', 'funding').count == 0
    store.close()


def test_out_of_range_funding_page_is_rejected_without_write(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class OutsideRange:
        def fetch_funding(self, symbol, start, end):
            return [
                {'fundingRateTimestamp': str(8 * HOUR), 'fundingRate': '0.0001'},
            ]
    engine = SyncEngine(
        store, OutsideRange(), clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 0)
    )
    assert result.state is SyncState.RETRYABLE
    assert store.coverage('BTCUSDT', 'funding').count == 0
    store.close()


def test_funding_schedule_change_uses_segment_boundaries(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0, 8 * HOUR])
    # Explicit schedule transitions require a segment-aware validator;
    # do not infer a single interval from the candle timeframe.
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': [(0, 8 * HOUR, 0), (8 * HOUR, HOUR, 0)]},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 8 * HOUR)
    )
    assert result.state is SyncState.READY
    assert store.coverage('BTCUSDT', 'funding').count == 2
    assert client.calls == [(0, 0), (8 * HOUR, 8 * HOUR)]
    store.close()


def test_single_segment_history_is_supported(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': [(0, 8 * HOUR, 0)]},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 0)
    )
    assert result.state is SyncState.READY
    assert client.calls == [(0, 0)]
    store.close()


def test_transition_missing_event_stays_partial(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0, 8 * HOUR, 10 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': [(0, 8 * HOUR, 0), (8 * HOUR, HOUR, 0)]},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 10 * HOUR)
    )
    assert result.state is SyncState.PARTIAL
    assert store.coverage('BTCUSDT', 'funding').count == 3
    store.close()


def test_transition_requires_schedule_covering_requested_start(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([8 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': [(8 * HOUR, HOUR, 0)]},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 8 * HOUR)
    )
    assert result.state is SyncState.UNAVAILABLE
    assert client.calls == []
    store.close()


def test_misaligned_funding_transition_fails_closed(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0, 8 * HOUR])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': [(0, 8 * HOUR, 0), (8 * HOUR + HOUR // 2, HOUR, 0)]},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 0, 10 * HOUR)
    )
    assert result.state is SyncState.REPAIR_REQUIRED
    assert 'aligned' in result.message
    assert client.calls == []
    store.close()


def test_unsorted_funding_transitions_fail_without_network(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    client = FundingClient([0])
    engine = SyncEngine(
        store, client, clock_ms=lambda: 20 * HOUR,
        funding_schedules={'BTCUSDT': [(8 * HOUR, HOUR, 0), (0, 8 * HOUR, 0)]},
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', 8 * HOUR, 10 * HOUR)
    )
    assert result.state is SyncState.REPAIR_REQUIRED
    assert client.calls == []
    store.close()


def test_current_funding_drift_reports_change_without_mutating_schedule(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    schedule = {'BTCUSDT': (8 * HOUR, 0)}
    engine = SyncEngine(store, Metadata(), funding_schedules=schedule)
    result = engine.check_current_funding_intervals()
    assert result['state'] is SyncState.REPAIR_REQUIRED
    assert result['changes']['BTCUSDT']['state'] == 'CHANGED'
    assert engine.funding_schedules == schedule
    assert schedule == {'BTCUSDT': (8 * HOUR, 0)}
    store.close()


def test_current_funding_drift_uses_latest_verified_segment(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        store, Metadata(),
        funding_schedules={'BTCUSDT': [(0, 8 * HOUR, 0), (8 * HOUR, HOUR, 0)]},
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    store.close()


def test_missing_current_funding_metadata_requires_review(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {}
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.check_current_funding_intervals()
    assert result['state'] is SyncState.REPAIR_REQUIRED
    assert result['changes']['BTCUSDT']['state'] == 'MISSING'
    store.close()


def test_current_funding_metadata_failure_is_retryable(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            raise ConnectionError('metadata unavailable')
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
    )
    result = engine.check_current_funding_intervals()
    assert result['state'] is SyncState.RETRYABLE
    assert engine.funding_schedules == {'BTCUSDT': (8 * HOUR, 0)}
    store.close()


def test_funding_drift_journal_survives_new_engine_instance(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    path = tmp_path / 'diagnostics' / 'funding-drift.jsonl'
    kwargs = dict(
        clock_ms=lambda: 123456789,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=path,
    )
    engine = SyncEngine(store, Metadata(), **kwargs)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]['observed_at_ms'] == 123456789
    assert records[0]['changes']['BTCUSDT']['state'] == 'CHANGED'
    engine_after_restart = SyncEngine(store, Metadata(), **kwargs)
    assert engine_after_restart.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert len(path.read_text().splitlines()) == 1
    store.close()


def test_funding_drift_journal_does_not_write_when_matching(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': 8 * HOUR}
    path = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=path,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    assert not path.exists()
    store.close()


def test_funding_drift_journal_failure_does_not_claim_success(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    parent_file = tmp_path / 'not_a_directory'
    parent_file.write_text('occupied')
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=parent_file / 'journal.jsonl',
    )
    result = engine.check_current_funding_intervals()
    assert result['state'] is SyncState.RETRYABLE
    assert result['changes']['BTCUSDT']['state'] == 'CHANGED'
    store.close()


def test_funding_drift_alert_recovery_after_restart(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    args = {'funding_schedules': {'BTCUSDT': (8 * HOUR, 0)},
            'funding_drift_journal': journal,
            'clock_ms': lambda: 1234}
    engine = SyncEngine(store, Metadata(), **args)
    assert engine.read_funding_drift_alerts()['state'] is SyncState.UNKNOWN
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    restarted = SyncEngine(store, Metadata(), **args)
    restored = restarted.read_funding_drift_alerts()
    assert restored['state'] is SyncState.REPAIR_REQUIRED
    assert restored['observed_at_ms'] == 1234
    assert restored['changes']['BTCUSDT']['state'] == 'CHANGED'
    store.close()


def test_funding_drift_journal_rotates_at_size_limit(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    import json
    valid = json.dumps({'observed_at_ms': 1, 'changes': {'BTCUSDT': {'state': 'CHANGED', 'current_interval_ms': 2 * HOUR}}}) + '\n'
    journal.write_text(valid * (1024 * 1024 // len(valid) + 1))
    engine = SyncEngine(
        store, Metadata(), clock_ms=lambda: 999,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert journal.with_name(journal.name + '.1').stat().st_size >= 1024 * 1024
    assert journal.stat().st_size < 1024 * 1024
    assert engine.read_funding_drift_alerts()['observed_at_ms'] == 999
    store.close()


def test_malformed_funding_drift_journal_fails_closed(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    journal = tmp_path / 'funding-drift.jsonl'
    journal.write_text('not json\\n')
    engine = SyncEngine(store, object(), funding_drift_journal=journal)
    assert engine.read_funding_drift_alerts()['state'] is SyncState.RETRYABLE
    store.close()


def test_funding_drift_recovery_ignores_truncated_tail(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    journal = tmp_path / 'funding-drift.jsonl'
    valid = {'observed_at_ms': 42, 'changes': {'BTCUSDT': {'state': 'CHANGED'}}}
    with journal.open('wb') as stream:
        stream.write((json.dumps(valid) + '\n').encode())
        stream.write(b'{"observed_at_ms": 999, "changes":')
    engine = SyncEngine(store, object(), funding_drift_journal=journal)
    recovered = engine.read_funding_drift_alerts()
    assert recovered['state'] is SyncState.REPAIR_REQUIRED
    assert recovered['observed_at_ms'] == 42
    store.close()


def test_funding_drift_recovery_rejects_only_truncated_record(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    journal = tmp_path / 'funding-drift.jsonl'
    journal.write_bytes(b'{"observed_at_ms": 999, "changes":')
    engine = SyncEngine(store, object(), funding_drift_journal=journal)
    assert engine.read_funding_drift_alerts()['state'] is SyncState.RETRYABLE
    store.close()


def test_funding_drift_journal_records_actual_changes_only(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        interval = HOUR
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': self.interval}
    client = Metadata()
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, client, clock_ms=lambda: 987,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert len(journal.read_text().splitlines()) == 1
    client.interval = 2 * HOUR
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]['changes']['BTCUSDT']['current_interval_ms'] == HOUR
    assert rows[1]['changes']['BTCUSDT']['current_interval_ms'] == 2 * HOUR
    store.close()
