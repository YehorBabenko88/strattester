"""Legacy read-only research runner.

This transitional Strattester consumer NEVER connects to Bybit or invokes
SyncEngine. Only the Grid owner may acquire and publish market history.
Callers must provide a pre-qualified, already populated snapshot/read store.
"""
from __future__ import annotations

from strattester.engine.executor import execute_strategy, requirements_ready


class ResearchRunner:
    def __init__(self, store, client=None, clock_ms=None):
        # Preserve the old signature only to reject unsafe existing callers
        # explicitly. Never silently fall back to independent acquisition.
        if client is not None:
            raise ValueError("GRID_SNAPSHOT_REQUIRED: direct exchange client forbidden")
        self.store = store

    def run(self, definition, instrument, *, start_ms: int | None = None,
            end_ms: int, checkpoint=None):
        symbol = instrument["symbol"]
        launch = int(instrument.get("launchTime") or 0)
        launch = (launch // 60_000) * 60_000
        start = launch if start_ms is None else max(launch, int(start_ms))
        if end_ms < start:
            raise ValueError("end_ms precedes instrument availability")
        # Read-only gate. Missing/gapped history is a refusal, not permission
        # for another market producer or for invented historical candles.
        if not requirements_ready(definition, self.store, symbol,
                                  start_ms=start, end_ms=end_ms):
            raise RuntimeError("GRID_HISTORY_NOT_READY")
        return execute_strategy(
            definition, self.store, symbol, checkpoint=checkpoint,
            start_ms=start, end_ms=end_ms,
        )
