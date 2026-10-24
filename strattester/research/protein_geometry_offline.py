"""Offline-only execution of geometry research over an existing store."""
from strattester.engine.executor import execute_strategy
from strattester.strategies.builtin.protein_geometry import protein_geometry_definition


def run_offline(store, symbol, *, start_ms=None, end_ms=None):
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("symbol required")
    return execute_strategy(protein_geometry_definition(), store, symbol,
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
