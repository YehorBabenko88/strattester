# Protein geometry strategy: modes and remaining gates

Strategy PROTEIN_GEOMETRY_RESEARCH v0.1.0 is disabled by default.
It accepts any symbol with complete 1m candles and returns geometry features,
not trade signals. No trading execution is authorized.

## Connected research
ResearchRunner calls SyncEngine for required history before execution.
No network calls originate from the strategy.

## Autonomous offline research
protein_geometry_offline.run_offline and run_universe_offline bypass SyncEngine.
The caller must provide an existing store. To guarantee read-only behavior,
supply a true immutable snapshot; SQLiteMarketStore.open() is NOT read-only:
it may initialize schema and WAL. Snapshot consistency across shards remains
an implementation gate.

## Outstanding work
- Universe discovery, delisted instruments, timeframe parameterization.
- Read-only snapshot adapter and consistency tests for shard routing.
- Expected timestamp spacing and incomplete/gap handling.
- Bounded memory and cancellation for large histories.
- Actual AlphaFold pair-attention model port and independent training.
- Visualization consumer and production-safe model versioning.
- Walk-forward OOS evaluation, negative controls, costs and statistical tests.

Do not merge or enable in production before these gates pass.
