# AlphaFold financial research / Grid interface audit

## Observed code boundaries (2026-10-24)
AlphaFold v2 source: google-deepmind/alphafold, model/modules.py,
model/folding.py, model/features.py, model/model.py.
Strattester: marketdata/sqlite_store.py, marketdata/store_factory.py,
research/runner.py, engine/executor.py, strategies/base.py.
Grid: grid/features.py, grid/rolling_event_features.py, grid/unified_features.py,
tests/test_market_math_research.py.

## Functional interpretation
AlphaFold's original structure module predicts protein atomic geometry from
biological representations. Its trained weights are not financial forecasting
weights. FinancialStructureBackend is an explicit dependency boundary;
no model backend, original inference, or training is present yet.
encode_market creates causal single/pair representations, not biological
amino-acid/MSA templates. Do not present it as running AlphaFold.

## Proposed adapter stages
1. Grid candle/event data -> canonical timestamp, instrument, timeframe,
   provenance, completeness and watermark.
2. Immutable snapshot -> causal single and pair embeddings with bounded N^2.
3. Financially trained Evoformer-inspired pair-update trunk (optional separate
   Linux GPU worker, pinned upstream commit and Apache-2.0 notices).
4. Financial head: future return distribution / volatility / regime.
5. Purged walk-forward, negative controls, fees and cross-instrument holdouts.
6. Only after independent QA: model registry and optional strategy activation.

## Unresolved synchronization contracts
- Grid feature timestamp semantics and event-time vs ingestion-time watermarks.
- Atomic snapshot of shard manifests and PostgreSQL / SQLite views.
- Shared symbol/market-type identity, candle close time and timeframe units.
- Idempotent checkpoint, exactly-once result publication, revision handling.
- CPU/GPU resource isolation, cancellation and stale model version fencing.
- Reproducible dataset hashes and model checkpoint provenance.

No claims of successful end-to-end Grid integration or predictive advantage.
