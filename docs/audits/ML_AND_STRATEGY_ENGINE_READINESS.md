# ML_AND_STRATEGY_ENGINE_READINESS

Independent review anchored to integrated PR #21 HEAD
`4f3a4bbb9a2f6c0cc3e87fbb0af4fed1dfcc3fd7`
and tree `5e8862ab22aa51055f96022c428b2d90f8b5abc2`.

**Decision: SOFTWARE_GATES_PASS / SYSTEM_ACCEPTANCE_BLOCKED / TRADING_NO_GO.**

## Evidence from original exact candidate

- GitHub tests workflow 40350795804: success.
- GitHub financial integration workflow 40350796074: failure by system acceptance gate; engineering gates reported successful.
- GitHub structural CPU workflow 40350796089: success.
- GitHub math workflow 40350796217: success.
- No real OOS, coherent live Grid history, GPU qualification or full native sandbox proof.

## Independent source audit (partial)

- Financial experiment: explicit horizon and availability checks, purged chronology, optional symbol holdout, train-only fitting, validation threshold, test evaluation, cancellation and bounded preparation.
- Financial training: bounded deterministic optimizer, finite checks, rollback on exception/cancel. Optimizer-state resume not established.
- Financial evaluation: independent simple-return roundtrip accounting, two-sided fees/slippage and flat nonnegative funding cost. This is not historical funding cashflow or an executable portfolio ledger.
- Independent analytic oracle and adversarial differential tests added in this branch.
- CLI, StrategyRegistry, ResearchRunner, SyncEngine, execute_strategy, checkpoint replay, storage routing and recovery still require complete source tracing; do not mark verified.

## P0 — blocking

1. Real OOS and externally coherent, revision/availability-proven historical snapshot missing.
2. Full native Windows sandbox and physical system acceptance missing.
3. Full ordinary strategy execution-path audit and real-data integration not yet evidenced.

## P1 — methodology

1. Signed historical funding events, liquidity, cash PnL and portfolio exposure accounting.
2. Cross-instrument/timeframe holdout and complete source-provenance leakage checks.
3. Nested hyperparameter selection, multiple comparisons and conditional calibration.
4. Crash/power-loss checkpoint and resume/recovery qualification.

## P2 — engineering

1. Expand independent reference oracles to train-only normalization and exact temporal interval sets.
2. Instrument/timeframe stratified negative controls and deterministic replay across platforms.
3. Resource limits and adversarial cancellation of every lifecycle stage.

## Test evidence for this audit branch

Tests added but not claimed PASS until a run is confirmed for the exact new HEAD.
No physical or production actions. No merge, no live execution, no production DB mutations.
