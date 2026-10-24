"""Offline-only execution of geometry research over an existing store."""
from strattester.engine.executor import execute_strategy


class _ReadOnlyStore:
    """Minimal capability boundary for the geometry strategy, not a process sandbox."""
    __slots__ = ('_coverage', '_iter_candles')

    def __init__(self, store):
        self._coverage = store.coverage
        self._iter_candles = store.iter_candles

    def coverage(self, *args, **kwargs):
        return self._coverage(*args, **kwargs)

    def iter_candles(self, *args, **kwargs):
        return self._iter_candles(*args, **kwargs)

from strattester.strategies.builtin.protein_geometry import protein_geometry_definition


def run_offline(store, symbol, *, start_ms=None, end_ms=None):
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("symbol required")
    return execute_strategy(protein_geometry_definition(), _ReadOnlyStore(store), symbol,
                            start_ms=start_ms, end_ms=end_ms)


def run_universe_offline(store, symbols, *, start_ms=None, end_ms=None):
    if isinstance(symbols, (str, bytes)):
        raise ValueError("symbols must be a sequence, not a string")
    results = {}
    for symbol in dict.fromkeys(symbols):
        try:
            results[symbol] = run_offline(store, symbol, start_ms=start_ms, end_ms=end_ms)
        except (ValueError, RuntimeError) as exc:
            results[symbol] = {"status": "BLOCKED", "reason": str(exc)}
    return results
