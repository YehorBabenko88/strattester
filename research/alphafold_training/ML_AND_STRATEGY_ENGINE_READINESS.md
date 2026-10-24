# ML_AND_STRATEGY_ENGINE_READINESS — independent partial audit

Date: 2026-10-24. Verdict: **NO-GO**.

## Immutable reference
- Integrated candidate PR #21: `67301726d250973602b964adabdb9eb8d50d0f13`.
- This audit is developed separately on `parallel/alphafold-training-backtest`, not merged into PR #21.
- PR #21 engineering matrix reported successful; financial-integration overall workflow deliberately failed system acceptance because coherent Grid snapshot, real OOS, GPU, and full upstream equivalence remain BLOCKED.
- No real-market profitability, GPU or production readiness claims.

## Source inspection completed
- `strattester/research/financial_experiment.py`: synthetic-only status; chronological purge; symbol holdout filtering; validation-selected threshold; test-only evaluation; walk-forward mode separation. Instrument holdout is optional; requires explicit acceptance policy and complete target/context provenance.
- `strattester/research/financial_training.py`: deterministic bounded Adam training; rollback on exception/cancel; finite gradients/weights; no optimizer checkpoint/resume proof.
- `strattester/research/financial_evaluation.py`: simple-return independent roundtrip ledger with two-sided fees/slippage; nonnegative per-horizon funding cost, not historical signed funding schedule. Gaussian NLL/MAE/coverage; no full calibration by instrument/regime.
- `strattester/research/financial_checkpoint.py`: tensor-only JSON, exclusive publish, trusted digest and shape validation; needs independent crash/concurrency and storage trust-boundary review.
- `research/alphafold_training`: separate baseline and walk-forward primitives; not interchangeable with structural neural training without adapter and frozen evaluation contract.

## Priorities
### P0 — acceptance blockers
1. No independently verified real-market OOS evidence or producer-issued coherent Grid historical snapshot.
2. No end-to-end proof of ordinary strategy registry -> requirements -> SyncEngine -> ResearchRunner -> execute_strategy -> checkpoint/cancellation -> simulation/backtest equivalence on the integrated HEAD. These paths have NOT been source-verified in this audit.
3. No authorized physical GPU evidence and no complete upstream equivalence.

### P1 — methodology and accounting
1. Mandatory instrument holdout policy, including context instruments, leakage, revisions and availability provenance.
2. Real funding events signed by side and event time; spread, latency, fill and portfolio ledger rather than a single per-horizon cost.
3. Multiple-testing adjustment and calibration diagnostics by instrument/timeframe/regime; out-of-fold threshold freeze and hyperparameter audit.
4. Crash-safe checkpoint registry, model/dataset digest linkage and cancellation evidence across complete strategy execution.

### P2 — follow-up hardening
1. Statistical intervals with dependency-aware blocks and documented selection bias.
2. Negative controls: label shuffle, delayed features, randomized signal, reversed labels, instrument/time shuffles.
3. CPU/GPU resource ceilings, independent math oracles, boundary and extreme-value tests.

## Independent additions in this branch
- `independent_oracles.py`: half-open label overlap; two-sided fill cost plus signed funding; analytic Gaussian NLL and calibration moments.
- `test_alphafold_training_independent_oracles.py`: adversarial reference checks.

## Evidence limitations
- The tests introduced by this audit are not claimed PASS until CI on the exact branch HEAD.
- No local or physical training, DB mutation, network trading, merge, or deployment performed.

## Cycle 2 training/backtest audit (2026-10-24)

Engineering changes on `cycle2/training-backtest` retain **NO-GO / real OOS BLOCKED**.
The experiment now admits the aggregate host preparation budget before producing
feature tensors, charges duplicate snapshots even when shared, bounds walk-forward
iterator materialization to 1025 examples/33 folds, and checks cancellation during
preparation, evaluation, fingerprinting and before checkpoint publication. Training
rejects an oversized logical tensor bank before cloning model state. This is a
conservative allocation admission policy, not a process RSS guarantee or a replacement
for operator workspace checks. Split boundaries, holdout context exclusion, batching,
validation-only threshold selection and JSON dataset identity are unchanged.

Dataset fingerprints stream the byte-identical existing canonical JSON array one
example at a time. No expanded snapshot dictionary bank is retained. Gaussian
scoring rejects nonfinite outputs from finite extreme inputs, including tiny scale.
Ledger documentation now states the implemented flat nonnegative funding charge;
no signed exchange funding schedule or leveraged liquidation is implemented.

P0: verified coherent historical input, authorized physical/GPU evidence and real
multi-instrument OOS remain BLOCKED. P1: aggregate allocation and extreme-score
fail-closed defects repaired; historical funding/fills/latency/portfolio accounting,
regime calibration and multiple-testing adjustment remain open. P2: streamed hash
compatibility, preparation cancellation, bounded iterator consumption, funding and
turnover regression coverage added. Existing tests retain chronological purge,
embargo, held-out context, sequential retraining policy and exclusive checkpoint replay.

The frozen real-data protocol is in `MULTI_INSTRUMENT_OOS_PROTOCOL.md`; it has not
been executed on unverified market data. Cycle 2 test evidence is recorded in the
PR body against the exact committed code SHA. Earlier audit evidence and its
limitations above describe their original historical revision.
