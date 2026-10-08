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
