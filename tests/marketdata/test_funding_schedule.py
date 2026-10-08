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
