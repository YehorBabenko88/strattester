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


def test_funding_drift_resolution_is_persisted_and_restored(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        interval = HOUR
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': self.interval}
    client = Metadata()
    journal = tmp_path / 'funding-drift.jsonl'
    kwargs = dict(
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
        clock_ms=lambda: 100,
    )
    engine = SyncEngine(store, client, **kwargs)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    client.interval = 8 * HOUR
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    restored = SyncEngine(store, client, **kwargs).read_funding_drift_alerts()
    assert restored['state'] is SyncState.READY
    assert restored['changes'] == {}
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[-1]['changes'] == {}
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    assert len(journal.read_text().splitlines()) == 2
    store.close()


def test_funding_drift_reappearing_after_resolution_creates_new_event(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        interval = HOUR
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': self.interval}
    client = Metadata()
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, client, funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    client.interval = 8 * HOUR
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    client.interval = HOUR
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert len(journal.read_text().splitlines()) == 3
    assert engine.read_funding_drift_alerts()['state'] is SyncState.REPAIR_REQUIRED
    store.close()


def test_funding_drift_journal_concurrent_threads_do_not_duplicate(tmp_path):
    import concurrent.futures
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    def run_check(_):
        engine = SyncEngine(
            store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
            funding_drift_journal=journal,
        )
        return engine.check_current_funding_intervals()['state']
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run_check, range(24)))
    assert all(state is SyncState.REPAIR_REQUIRED for state in results)
    assert len(journal.read_text().splitlines()) == 1
    store.close()


def test_funding_drift_recovers_rotated_generation_after_crash(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    journal = tmp_path / 'funding-drift.jsonl'
    rotated = journal.with_name(journal.name + '.1')
    rotated.write_text(json.dumps({
        'observed_at_ms': 42,
        'changes': {'BTCUSDT': {'state': 'CHANGED'}},
    }) + '\n')
    engine = SyncEngine(store, object(), funding_drift_journal=journal)
    assert engine.read_funding_drift_alerts()['observed_at_ms'] == 42
    journal.touch()
    assert engine.read_funding_drift_alerts()['observed_at_ms'] == 42
    store.close()


def test_funding_drift_main_generation_precedes_rotated_history(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    journal = tmp_path / 'funding-drift.jsonl'
    journal.with_name(journal.name + '.1').write_text(json.dumps({
        'observed_at_ms': 1, 'changes': {'BTCUSDT': {'state': 'CHANGED'}},
    }) + '\n')
    journal.write_text(json.dumps({
        'observed_at_ms': 2, 'changes': {},
    }) + '\n')
    engine = SyncEngine(store, object(), funding_drift_journal=journal)
    recovered = engine.read_funding_drift_alerts()
    assert recovered['state'] is SyncState.READY
    assert recovered['observed_at_ms'] == 2
    store.close()


def test_segmented_funding_window_without_any_event_not_ready(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    engine = SyncEngine(
        store, FundingClient([]), clock_ms=lambda: 100 * HOUR,
        funding_schedules={
            'BTCUSDT': [(0, 8 * HOUR, 0), (32 * HOUR, 4 * HOUR, 0)]
        },
    )
    result = engine.sync_requirement(
        DataRequirement('BTCUSDT', 'funding', '1m', HOUR, 2 * HOUR)
    )
    assert result.state is SyncState.REPAIR_REQUIRED
    assert 'no scheduled funding event' in result.message
    store.close()


def test_funding_drift_new_event_after_truncated_tail_is_recoverable(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        interval = HOUR
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': self.interval}
    client = Metadata()
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, client, clock_ms=lambda: 123,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    with journal.open('ab') as stream:
        stream.write(b'{"incomplete":')
    client.interval = 2 * HOUR
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    recovered = SyncEngine(
        store, client, funding_drift_journal=journal,
    ).read_funding_drift_alerts()
    assert recovered['state'] is SyncState.REPAIR_REQUIRED
    assert recovered['changes']['BTCUSDT']['current_interval_ms'] == 2 * HOUR
    assert journal.with_name(journal.name + '.1').exists()
    assert len([json.loads(line) for line in journal.read_text().splitlines()]) == 1
    store.close()


def test_funding_drift_unchanged_alert_with_truncated_tail_self_heals(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    with journal.open('ab') as stream:
        stream.write(b'partial')
    result = engine.check_current_funding_intervals()
    assert result['state'] is SyncState.REPAIR_REQUIRED
    assert journal.with_name(journal.name + '.1').exists()
    assert len(journal.read_text().splitlines()) == 1
    assert engine.read_funding_drift_alerts()['state'] is SyncState.REPAIR_REQUIRED
    store.close()


def test_funding_drift_resolution_self_heals_truncated_tail(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        interval = HOUR
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': self.interval}
    client = Metadata()
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, client, funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    client.interval = 8 * HOUR
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    with journal.open('ab') as stream:
        stream.write(b'{"unfinished":')
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    assert engine.read_funding_drift_alerts()['state'] is SyncState.READY
    assert journal.with_name(journal.name + '.1').exists()
    store.close()


def _funding_drift_process_check(journal_path):
    """Independent process worker; safe for Windows spawn."""
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal_path,
    )
    result = engine.check_current_funding_intervals()
    return result['state'].value, result.get('message', '')


def test_funding_drift_journal_deduplicates_across_processes(tmp_path):
    import concurrent.futures
    import multiprocessing
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    ctx = multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=ctx) as pool:
        results = list(pool.map(_funding_drift_process_check, [str(journal)] * 8))
    assert all(state == SyncState.REPAIR_REQUIRED.value for state, _ in results), results
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]['changes']['BTCUSDT']['state'] == 'CHANGED'


def test_funding_drift_concurrent_rotation_keeps_one_new_event(tmp_path):
    import concurrent.futures
    import multiprocessing
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    previous = json.dumps({
        'observed_at_ms': 1,
        'changes': {'BTCUSDT': {
            'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
            'current_interval_ms': 2 * HOUR,
        }},
    }) + '\n'
    journal.write_text(previous * (1024 * 1024 // len(previous) + 1))
    ctx = multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=ctx) as pool:
        results = list(pool.map(_funding_drift_process_check, [str(journal)] * 8))
    assert all(state == SyncState.REPAIR_REQUIRED.value for state, _ in results), results
    assert journal.with_name(journal.name + '.1').stat().st_size >= 1024 * 1024
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]['changes']['BTCUSDT']['current_interval_ms'] == HOUR


def test_funding_drift_rotation_keeps_only_one_backup_generation(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        interval = HOUR
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': self.interval}
    client = Metadata()
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, client, funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    for interval in (HOUR, 2 * HOUR, 4 * HOUR):
        client.interval = interval
        if journal.exists():
            with journal.open('a') as stream:
                stream.write(
                    (json.dumps({'observed_at_ms': 1, 'changes': {
                        'BTCUSDT': {'state': 'CHANGED', 'current_interval_ms': 3 * HOUR},
                    }}) + '\n') * 10000
                )
        assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert journal.with_name(journal.name + '.1').exists()
    assert not journal.with_name(journal.name + '.2').exists()
    assert len([json.loads(line) for line in journal.read_text().splitlines()]) == 1
    assert engine.read_funding_drift_alerts()['changes']['BTCUSDT']['current_interval_ms'] == 4 * HOUR
    store.close()


def test_funding_drift_reader_recovers_after_active_file_disappears(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    journal = tmp_path / 'funding-drift.jsonl'
    rotated = journal.with_name(journal.name + '.1')
    rotated.write_text(json.dumps({
        'observed_at_ms': 77, 'changes': {'BTCUSDT': {'state': 'CHANGED'}},
    }) + '\n')
    engine = SyncEngine(store, object(), funding_drift_journal=journal)
    original_open = Path.open
    def open_with_rotation_race(path, *args, **kwargs):
        if path == journal:
            raise FileNotFoundError('active journal moved during rotation')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', open_with_rotation_race)
    result = engine.read_funding_drift_alerts()
    assert result['state'] is SyncState.REPAIR_REQUIRED
    assert result['observed_at_ms'] == 77
    store.close()


def test_funding_drift_first_check_with_lock_but_no_journal_is_clean(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': 8 * HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    assert not journal.exists()
    assert engine.read_funding_drift_alerts()['state'] is SyncState.UNKNOWN
    store.close()


def test_funding_drift_missing_both_generations_after_persist_fails_closed(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert journal.with_name(journal.name + '.initialized').exists()
    journal.unlink()
    recovered = SyncEngine(
        store, Metadata(), funding_drift_journal=journal,
    ).read_funding_drift_alerts()
    assert recovered['state'] is SyncState.RETRYABLE
    assert 'missing' in recovered['message']
    assert engine.check_current_funding_intervals()['state'] is SyncState.RETRYABLE
    store.close()


def test_funding_drift_first_check_does_not_create_initialization_marker(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': 8 * HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.READY
    assert not journal.with_name(journal.name + '.initialized').exists()
    store.close()


def test_funding_drift_recreates_missing_marker_without_duplicate_event(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    marker = journal.with_name(journal.name + '.initialized')
    marker.unlink()
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert marker.exists()
    assert len([json.loads(line) for line in journal.read_text().splitlines()]) == 1
    store.close()


def test_funding_drift_repairs_partial_initialization_marker(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    marker = journal.with_name(journal.name + '.initialized')
    marker.write_bytes(b'')
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert marker.read_bytes() == b'1\n'
    assert len([json.loads(line) for line in journal.read_text().splitlines()]) == 1
    store.close()


def test_funding_drift_marker_write_failure_is_retryable(tmp_path, monkeypatch):
    from pathlib import Path
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    original_open = Path.open
    marker = journal.with_name(journal.name + '.initialized')
    def deny_marker(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get('mode', 'r')
        if path == marker and any(flag in mode for flag in ('w', 'a', 'x', '+')):
            raise PermissionError('simulated marker write denial')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', deny_marker)
    result = engine.check_current_funding_intervals()
    assert result['state'] is SyncState.RETRYABLE
    assert journal.exists()
    monkeypatch.setattr(Path, 'open', original_open)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert marker.read_bytes() == b'1\n'
    store.close()


def test_funding_drift_repairs_truncated_marker_after_restart(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    marker = journal.with_name(journal.name + '.initialized')
    marker.write_bytes(b'1')
    restarted = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert restarted.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert marker.read_bytes() == b'1\n'
    assert len([json.loads(line) for line in journal.read_text().splitlines()]) == 1
    store.close()


def test_funding_drift_missing_journal_inaccessible_marker_fails_closed(tmp_path, monkeypatch):
    from pathlib import Path
    journal = tmp_path / 'funding-drift.jsonl'
    marker = journal.with_name(journal.name + '.initialized')
    engine = SyncEngine(None, object(), funding_drift_journal=journal)
    original_open = Path.open
    def deny_marker(path, *args, **kwargs):
        if path == marker:
            raise PermissionError('simulated inaccessible marker')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', deny_marker)
    result = engine.read_funding_drift_alerts()
    assert result['state'] is SyncState.RETRYABLE
    assert 'inaccessible' in result['message']
    monkeypatch.setattr(Path, 'open', original_open)
    assert engine.read_funding_drift_alerts()['state'] is SyncState.UNKNOWN


def test_funding_drift_partial_marker_write_denial_preserves_event(tmp_path, monkeypatch):
    from pathlib import Path
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    marker = journal.with_name(journal.name + '.initialized')
    marker.write_bytes(b'')
    original_open = Path.open
    def deny_marker_writes(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get('mode', 'r')
        if path == marker and any(flag in mode for flag in ('w', 'a', 'x', '+')):
            raise PermissionError('simulated marker repair denial')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', deny_marker_writes)
    assert engine.check_current_funding_intervals()['state'] is SyncState.RETRYABLE
    assert len(journal.read_text().splitlines()) == 1
    monkeypatch.setattr(Path, 'open', original_open)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert marker.read_bytes() == b'1\n'
    assert len(journal.read_text().splitlines()) == 1
    store.close()


def test_funding_drift_backup_only_recreates_active_generation(tmp_path):
    import json
    store = SQLiteMarketStore.open(tmp_path / 'funding.db')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    journal = tmp_path / 'funding-drift.jsonl'
    engine = SyncEngine(
        store, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    backup = journal.with_name(journal.name + '.1')
    journal.replace(backup)
    assert not journal.exists()
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert journal.exists()
    assert len([json.loads(line) for line in journal.read_text().splitlines()]) == 1
    backup.unlink()
    assert engine.read_funding_drift_alerts()['state'] is SyncState.REPAIR_REQUIRED
    store.close()


def test_funding_drift_backup_only_concurrent_process_recovery(tmp_path):
    import concurrent.futures
    import json
    import multiprocessing
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    backup.write_text(json.dumps({'observed_at_ms': 10, 'changes': changes}) + '\n')
    ctx = multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=ctx) as pool:
        results = list(pool.map(_funding_drift_process_check, [str(journal)] * 8))
    assert all(state == SyncState.REPAIR_REQUIRED.value for state, _ in results), results
    assert len(journal.read_text().splitlines()) == 1
    assert json.loads(journal.read_text().splitlines()[0])['changes'] == changes
    assert json.loads(backup.read_text().splitlines()[0])['changes'] == changes
    assert journal.with_name(journal.name + '.initialized').read_bytes() == b'1\n'


def test_funding_drift_backup_survives_failed_active_recreation(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    backup.write_text(json.dumps({'observed_at_ms': 10, 'changes': changes}) + '\n')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    original_open = Path.open
    def deny_active_write(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get('mode', 'r')
        if path == journal and any(flag in mode for flag in ('w', 'a', 'x', '+')):
            raise OSError('simulated active journal disk failure')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', deny_active_write)
    failed = engine.check_current_funding_intervals()
    assert failed['state'] is SyncState.RETRYABLE
    assert not journal.exists()
    assert json.loads(backup.read_text().splitlines()[0])['changes'] == changes
    assert engine.read_funding_drift_alerts()['state'] is SyncState.REPAIR_REQUIRED
    monkeypatch.setattr(Path, 'open', original_open)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert json.loads(journal.read_text().splitlines()[0])['changes'] == changes
    assert json.loads(backup.read_text().splitlines()[0])['changes'] == changes


def test_funding_drift_empty_active_generation_recovers_from_backup(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    backup.write_text(json.dumps({'observed_at_ms': 10, 'changes': changes}) + '\n')
    journal.touch()
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert len(journal.read_text().splitlines()) == 1
    assert json.loads(journal.read_text().splitlines()[0])['changes'] == changes
    backup.unlink()
    assert engine.read_funding_drift_alerts()['state'] is SyncState.REPAIR_REQUIRED


def test_funding_drift_repairs_oversized_marker_without_duplicate_event(tmp_path):
    journal = tmp_path / 'funding-drift.jsonl'
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    marker = journal.with_name(journal.name + '.initialized')
    marker.write_bytes(b'corrupted' * 131072)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert marker.read_bytes() == b'1\n'
    assert len(journal.read_text().splitlines()) == 1


def test_funding_drift_tail_inspection_permission_failure_is_retryable(tmp_path, monkeypatch):
    from pathlib import Path
    journal = tmp_path / 'funding-drift.jsonl'
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    original_open = Path.open
    calls = {'reads': 0}
    def deny_second_read(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get('mode', 'r')
        if path == journal and mode == 'rb':
            calls['reads'] += 1
            if calls['reads'] == 2:
                raise PermissionError('simulated journal tail read failure')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', deny_second_read)
    result = engine.check_current_funding_intervals()
    assert result['state'] is SyncState.RETRYABLE
    assert 'inspection failed' in result['message']
    assert len(journal.read_text().splitlines()) == 1
    monkeypatch.setattr(Path, 'open', original_open)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert len(journal.read_text().splitlines()) == 1


def test_funding_drift_corrupt_both_generations_fails_closed(tmp_path):
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    journal.write_bytes(b'not json\n')
    backup.write_bytes(b'also not json\n')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.read_funding_drift_alerts()['state'] is SyncState.RETRYABLE
    assert engine.check_current_funding_intervals()['state'] is SyncState.RETRYABLE
    assert journal.read_bytes() == b'not json\n'
    assert backup.read_bytes() == b'also not json\n'


def test_funding_drift_corrupt_active_recovers_valid_backup(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    backup.write_text(json.dumps({'observed_at_ms': 10, 'changes': changes}) + '\n')
    journal.write_bytes(b'corrupt record\n')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    recovered = engine.read_funding_drift_alerts()
    assert recovered['state'] is SyncState.REPAIR_REQUIRED
    assert recovered['observed_at_ms'] == 10
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert json.loads(backup.read_text().splitlines()[0])['changes'] == changes


def test_funding_drift_recovery_skips_invalid_symbol_payload(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    valid = {'observed_at_ms': 10, 'changes': {'BTCUSDT': {'state': 'CHANGED'}}}
    invalid = {'observed_at_ms': 20, 'changes': {'BTCUSDT': ['not a drift record']}}
    journal.write_text(json.dumps(valid) + '\n' + json.dumps(invalid) + '\n')
    engine = SyncEngine(None, object(), funding_drift_journal=journal)
    recovered = engine.read_funding_drift_alerts()
    assert recovered['state'] is SyncState.REPAIR_REQUIRED
    assert recovered['observed_at_ms'] == 10
    assert recovered['changes'] == valid['changes']


def test_funding_drift_recovery_rejects_only_invalid_symbol_payloads(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    journal.write_text(json.dumps({
        'observed_at_ms': 20,
        'changes': {'BTCUSDT': {'state': 'UNRECOGNIZED'}},
    }) + '\n')
    engine = SyncEngine(None, object(), funding_drift_journal=journal)
    assert engine.read_funding_drift_alerts()['state'] is SyncState.RETRYABLE


def test_funding_drift_recovery_rejects_invalid_changed_intervals(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    valid = {'observed_at_ms': 10, 'changes': {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}}
    invalid = [
        {'state': 'CHANGED', 'verified_interval_ms': True, 'current_interval_ms': HOUR},
        {'state': 'CHANGED', 'verified_interval_ms': -1, 'current_interval_ms': HOUR},
        {'state': 'CHANGED', 'verified_interval_ms': HOUR, 'current_interval_ms': HOUR},
        {'state': 'CHANGED', 'current_interval_ms': 0},
        {'state': 'CHANGED', 'verified_interval_ms': 'bad'},
    ]
    engine = SyncEngine(None, object(), funding_drift_journal=journal)
    for detail in invalid:
        journal.write_text(json.dumps(valid) + '\n' +
                           json.dumps({'observed_at_ms': 20, 'changes': {'BTCUSDT': detail}}) + '\n')
        recovered = engine.read_funding_drift_alerts()
        assert recovered['state'] is SyncState.REPAIR_REQUIRED
        assert recovered['observed_at_ms'] == 10
        assert recovered['changes'] == valid['changes']


def test_funding_drift_recovery_accepts_legacy_partial_changed_interval(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    journal.write_text(json.dumps({
        'observed_at_ms': 11,
        'changes': {'BTCUSDT': {'state': 'CHANGED', 'current_interval_ms': 2 * HOUR}},
    }) + '\n')
    recovered = SyncEngine(None, object(), funding_drift_journal=journal).read_funding_drift_alerts()
    assert recovered['state'] is SyncState.REPAIR_REQUIRED
    assert recovered['observed_at_ms'] == 11


def test_funding_drift_torn_active_keeps_valid_backup(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    original = json.dumps({'observed_at_ms': 10, 'changes': changes}) + '\n'
    backup.write_text(original)
    journal.write_bytes(b'{"observed_at_ms":')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert backup.read_text() == original
    assert journal.with_name(journal.name + '.partial').read_bytes() == b'{"observed_at_ms":'
    assert len(journal.read_text().splitlines()) == 1
    assert engine.read_funding_drift_alerts()['state'] is SyncState.REPAIR_REQUIRED


def test_funding_drift_torn_active_failed_recreation_keeps_backup(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    original = json.dumps({'observed_at_ms': 10, 'changes': changes}) + '\n'
    backup.write_text(original)
    journal.write_bytes(b'{"observed_at_ms":')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    original_open = Path.open
    def deny_recreation(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get('mode', 'r')
        if path == journal and mode == 'a':
            raise PermissionError('simulated append denial')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', deny_recreation)
    failed = engine.check_current_funding_intervals()
    assert failed['state'] is SyncState.RETRYABLE
    assert backup.read_text() == original
    assert engine.read_funding_drift_alerts()['observed_at_ms'] == 10
    monkeypatch.setattr(Path, 'open', original_open)
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert backup.read_text() == original
    assert len(journal.read_text().splitlines()) == 1


def test_funding_drift_repeated_torn_active_repairs_keep_backup(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    original = json.dumps({'observed_at_ms': 10, 'changes': changes}) + '\n'
    backup.write_text(original)
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    for attempt in range(3):
        journal.write_bytes(b'{"observed_at_ms":')
        assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
        assert backup.read_text() == original
        assert engine.read_funding_drift_alerts()['state'] is SyncState.REPAIR_REQUIRED
        assert len(journal.read_text().splitlines()) == 1
        assert journal.with_name(journal.name + '.partial').read_bytes() == b'{"observed_at_ms":'
    assert len(list(tmp_path.glob('funding-drift.jsonl.partial*'))) == 1


def test_funding_drift_torn_active_without_backup_is_not_silently_accepted(tmp_path):
    journal = tmp_path / 'funding-drift.jsonl'
    journal.write_bytes(b'{"observed_at_ms":')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.read_funding_drift_alerts()['state'] is SyncState.RETRYABLE
    assert engine.check_current_funding_intervals()['state'] is SyncState.RETRYABLE
    assert journal.read_bytes() == b'{"observed_at_ms":'
    assert not journal.with_name(journal.name + '.1').exists()


def test_funding_drift_torn_active_with_corrupt_backup_fails_closed(tmp_path):
    journal = tmp_path / 'funding-drift.jsonl'
    backup = journal.with_name(journal.name + '.1')
    journal.write_bytes(b'{"observed_at_ms":')
    backup.write_bytes(b'bad backup\n')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.read_funding_drift_alerts()['state'] is SyncState.RETRYABLE
    assert engine.check_current_funding_intervals()['state'] is SyncState.RETRYABLE
    assert journal.read_bytes() == b'{"observed_at_ms":'
    assert backup.read_bytes() == b'bad backup\n'


def test_funding_drift_invalid_complete_final_line_is_not_deduplicated(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    journal.write_text(json.dumps({'observed_at_ms': 10, 'changes': changes}) +
                       '\n' + 'invalid complete record\n')
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), clock_ms=lambda: 20,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    recovered = engine.read_funding_drift_alerts()
    assert recovered['observed_at_ms'] == 20
    assert recovered['changes'] == changes
    assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
    assert len(journal.read_text().splitlines()) == 3


def test_funding_drift_invalid_final_timestamp_is_not_deduplicated(tmp_path):
    import json
    journal = tmp_path / 'funding-drift.jsonl'
    changes = {'BTCUSDT': {
        'state': 'CHANGED', 'verified_interval_ms': 8 * HOUR,
        'current_interval_ms': HOUR,
    }}
    valid = {'observed_at_ms': 10, 'changes': changes}
    class Metadata:
        def fetch_current_funding_intervals(self):
            return {'BTCUSDT': HOUR}
    engine = SyncEngine(
        None, Metadata(), clock_ms=lambda: 30,
        funding_schedules={'BTCUSDT': (8 * HOUR, 0)},
        funding_drift_journal=journal,
    )
    for invalid_time in (True, -1, '20'):
        journal.write_text(json.dumps(valid) + '\n' +
                           json.dumps({'observed_at_ms': invalid_time, 'changes': changes}) + '\n')
        assert engine.check_current_funding_intervals()['state'] is SyncState.REPAIR_REQUIRED
        assert engine.read_funding_drift_alerts()['observed_at_ms'] == 30
        assert len(journal.read_text().splitlines()) == 3
