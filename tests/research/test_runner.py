"""Read-only Strattester consumer tests; Grid is the only market producer."""
import pytest
from strattester.research.runner import ResearchRunner
from strattester.marketdata.sqlite_store import SQLiteMarketStore, Candle
from strattester.strategies.base import StrategyDefinition, DataRequirement


class NeedsMark:
    def run_context(self, context, checkpoint=None):
        return (
            context.coverage("candles", "1m").count,
            context.coverage("mark_price", "1m").count,
        )


def definition():
    return StrategyDefinition("needs-mark", "1", (
        DataRequirement("candles", ("1m",)),
        DataRequirement("mark_price", ("1m",)),
    ), NeedsMark)


def test_runner_requires_terminan_engine_after_readiness_without_mutation(tmp_path):
    s = SQLiteMarketStore.open(tmp_path / "m.db")
    try:
        runner = ResearchRunner(s)
        d = definition()
        changes = s.connection.total_changes
        with pytest.raises(RuntimeError, match="GRID_HISTORY_NOT_READY"):
            runner.run(d, {"symbol": "BTCUSDT", "launchTime": "0"},
                       start_ms=0, end_ms=60_000)
        assert s.connection.total_changes == changes

        # Preloaded source rows are historical fixtures, not source-attested
        # Grid evidence; they cannot authorize an independent strategy engine.
        rows = [
            Candle("BTCUSDT", "1m", 0, 100, 101, 99, 100, 1, 100, True),
            Candle("BTCUSDT", "1m", 60_000, 100, 101, 99, 100, 1, 100, True),
        ]
        assert s.upsert_candles(rows).accepted == 2
        assert s.upsert_price_klines("mark_price", "BTCUSDT", [
            ["0", "100", "101", "99", "100"],
            ["60000", "100", "101", "99", "100"],
        ], "1m").accepted == 2
        before = s.connection.total_changes
        for _ in range(2):
            with pytest.raises(RuntimeError, match="TERMINAN_EXECUTION_API_REQUIRED"):
                runner.run(d, {"symbol": "BTCUSDT", "launchTime": "0"},
                           start_ms=0, end_ms=60_000)
            assert s.connection.total_changes == before
    finally:
        s.close()


def test_legacy_client_rejected_before_exchange_calls(tmp_path):
    class ForbiddenBybit:
        def fetch_klines(self, *args, **kwargs):
            raise AssertionError("unexpected market request")

        def fetch_mark_klines(self, *args, **kwargs):
            raise AssertionError("unexpected mark request")

    s = SQLiteMarketStore.open(tmp_path / "existing.db")
    try:
        before = s.connection.total_changes
        with pytest.raises(ValueError, match="GRID_SNAPSHOT_REQUIRED"):
            ResearchRunner(s, ForbiddenBybit())
        assert s.connection.total_changes == before
    finally:
        s.close()


def test_partial_history_does_not_become_ready(tmp_path):
    s = SQLiteMarketStore.open(tmp_path / "partial.db")
    try:
        s.upsert_candles([
            Candle("BTCUSDT", "1m", 0, 100, 101, 99, 100, 1, 100, True),
        ])
        before = s.connection.total_changes
        with pytest.raises(RuntimeError, match="GRID_HISTORY_NOT_READY"):
            ResearchRunner(s).run(
                definition(), {"symbol": "BTCUSDT", "launchTime": "0"},
                start_ms=0, end_ms=60_000,
            )
        assert s.connection.total_changes == before
    finally:
        s.close()
