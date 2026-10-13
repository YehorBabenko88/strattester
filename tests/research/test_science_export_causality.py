import json

import pytest

from strattester.marketdata.sqlite_store import Candle, SQLiteMarketStore
from strattester.research.scalp_bootstrap import historical_scalp_events
from strattester.research.scientific_bootstrap import export_scientific_bootstrap


def level_bars(n=32):
    rows = [dict(t=i * 60000, open=100., high=100.1, low=99.9,
                 close=100., volume=100., turnover=10000.) for i in range(n)]
    rows[5]['high'] = 100.2
    return rows


def event_at(rows, timestamp=1200000):
    return next(x for x in historical_scalp_events(rows, symbol='BTCUSDT')
                if x['event_ts_ms'] == timestamp)


@pytest.mark.parametrize('next_close,target', [(101., 'BREAKOUT'), (99., 'REJECTION')])
def test_future_return_changes_outcome_without_changing_known_event(next_close, target):
    rows = level_bars()
    before = event_at(rows)
    rows[21].update(close=next_close, high=max(100.1, next_close),
                    low=min(99.9, next_close))
    after = event_at(rows)
    assert before['state'] == after['state'] == 'LEVEL_APPROACH'
    assert before['features'] == after['features']
    assert before['known_at_ms'] == after['known_at_ms'] == 1260000
    assert after['outcome']['next_1m_state'] == target
    assert after['outcome']['next_1m_return_bps'] == pytest.approx(
        100 if next_close == 101 else -100)
    assert after['outcome_known_at_ms'] == 1320000


def test_appending_future_bar_preserves_current_event_and_adds_future_target():
    rows = level_bars()
    prefix = event_at(rows[:30], 1740000)
    rows[30].update(close=101., high=101.)
    extended = event_at(rows, 1740000)
    assert prefix['state'] == extended['state'] == 'LEVEL_APPROACH'
    assert prefix['features'] == extended['features']
    assert prefix['known_at_ms'] == extended['known_at_ms'] == 1800000
    assert prefix['outcome'] == {'next_1m_return_bps': None, 'next_1m_state': None}
    assert prefix['outcome_known_at_ms'] is None
    assert extended['outcome']['next_1m_state'] == 'BREAKOUT'
    assert extended['outcome_known_at_ms'] == 1860000


def test_impulse_state_remains_current_even_when_future_target_is_rejection():
    rows = level_bars()
    rows[20]['volume'] = 200.
    rows[21].update(close=99., low=99.)
    event = event_at(rows)
    assert event['state'] == 'IMPULSE_BUILDUP'
    assert event['known_at_ms'] == 1260000
    assert event['outcome']['next_1m_state'] == 'REJECTION'
    assert event['outcome_known_at_ms'] == 1320000


def test_exported_poc_snapshot_is_known_at_last_candle_close(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / 'market.sqlite3')
    try:
        store.upsert_candles([Candle('BTCUSDT', '1m', b['t'], b['open'], b['high'],
                                    b['low'], b['close'], b['volume'], b['turnover'])
                             for b in level_bars(42)])
        output = tmp_path / 'science.json'
        export_scientific_bootstrap(store, ['BTCUSDT'], output)
        symbol = json.loads(output.read_text(encoding='utf-8'))['symbols'][0]
        profile = symbol['summary']['latest_poc_proxy']
        assert profile['known_at'] == 2520000
        assert profile['poc'] == 100.
        assert profile['mode'] == 'POC_PROXY'
        assert symbol['through_ms'] == 2460000
    finally:
        store.close()
