# AlphaFold-inspired financial research acceptance

Status: **NO-GO / RESEARCH_UNVERIFIED**.

## Required offline verification

Run from repository root:

```bash
python -m compileall -q research/alphafold_training
python -m unittest discover -s tests -p 'test_alphafold_training_*.py' -v
```

These commands are instructions, not evidence of a passing run.

## Current boundaries

- This is not the original AlphaFold backend and does not prove predictive value.
- Never select thresholds, features, model hyperparameters or stopping criteria on OOS test.
- Model factory must return a fresh instance per fold; no model may retain fitted state across folds.
- Labels and features must have documented event time, publication time, ingestion time, and correction provenance before accepting real Grid data.
- The present net-return calculator is a simplified, non-overlapping horizon model, not an executable trading simulator.
- Fee and slippage parameters must be justified by historical execution evidence.
- The exploratory block bootstrap does not adjust for multiple testing, cross-instrument dependence or regime selection.
- SHA256 checks integrity only; do not deserialize untrusted pickle/torch artifacts.
- No live exchange credentials, production DB writes, online model weight fetching, or real orders.

## Blocking acceptance gates

1. Python compilation and all adversarial tests pass on the exact commit.
2. Immutable snapshot and independent dataset SHA256 evidence.
3. Time-consistent event/feature/label lineage, purged cross-instrument folds and disjoint OOS windows.
4. Train-only preprocessing and nested validation with frozen OOS test.
5. Multiple baselines and controls, with confidence intervals and multiple-hypothesis adjustment.
6. Per-instrument, timeframe, market-type, regime and fee sensitivity analysis.
7. Full trade-ledger accounting, funding, liquidity, turnover and portfolio exposure constraints.
8. Safe versioned model registry with verified byte hashes and trusted artifact loading.
9. CPU/GPU reproducibility, cancellation, resource bounds and no-network/no-trading side-effect tests.

No claim of a completed pipeline or profitability is authorized before these gates are evidenced.
