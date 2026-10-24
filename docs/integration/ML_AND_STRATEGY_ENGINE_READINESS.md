# ML_AND_STRATEGY_ENGINE_READINESS — integration audit

Reference integrated PR #21: `67301726d250973602b964adabdb9eb8d50d0f13`.
Integration audit branch: `parallel/alphafold-training-backtest-pr21-integration`.

**Verdict: NO-GO — RESEARCH ONLY.**

## Verified source contracts
- `StrategyRegistry.register` enforces unique (id, version); `set_enabled` is a mutable registry flag.
- `ResearchRunner.run` invokes `SyncEngine` for requirements and then `execute_strategy`.
- `execute_strategy` checks history coverage but **does not enforce `definition.enabled`**. Do not treat disabled registration as an authorization boundary.
- `StrategyContext.candles` exposes legacy market records, not verified producer-signed financial snapshots.
- `financial_pipeline.predict_snapshot` checks trusted checkpoint fingerprint, horizon and typed snapshot contract.
- `financial_experiment` trains a fresh structural model and selects a validation threshold; its output is explicitly synthetic engineering only.
- `financial_evaluation` uses simple returns and a nonnegative funding-cost stress assumption, not exchange-event funding settlement.

## Implemented in this integration audit
- Independent roundtrip and Gaussian reference oracle tests.
- Explicit multi-instrument offline research specification with horizon, timeframe, version and resource limits.
- Separate disabled-by-default AlphaFold Financial strategy definition, whose legacy context fails closed.

## P0
1. No verified real OOS, coherent Grid snapshot, GPU acceptance or complete upstream parity.
2. Ordinary strategy execution path cannot be treated as research-only security boundary: executor ignores `enabled`.
3. No verified native conversion from legacy strategy data into typed financial snapshots with full provenance.

## P1
1. Research-only authorization must be enforced at execution entry points, not merely by registration metadata.
2. Real signed funding event ledger, fees/slippage/turnover/terminal liquidation and portfolio accounting remain incomplete.
3. Independent calibration by instrument/timeframe/regime, nested hyperparameter selection and multiple-comparison correction remain incomplete.
4. Resume/recovery and cancellation must be validated end-to-end across persisted checkpoints.

## P2
1. Broader cross-timeframe holdout, adversarial revision and late-availability controls.
2. CPU/GPU determinism and performance/resource regression matrix.
3. Additional statistical negative controls and block-bootstrap sensitivity.

## Acceptance protocol
Do not promote to live. Obtain trusted producer-issued snapshots, freeze dataset/model hashes, run historical walk-forward with disjoint OOS, fit fresh models per fold, compare controls and baselines, then require independently checked financial ledger and CI evidence on the exact accepted HEAD.

CI outcomes on this branch must be checked independently; synthetic metrics are not evidence of trading profitability.
