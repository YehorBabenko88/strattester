# Frozen multi-instrument OOS protocol — pending verified inputs

Status: BLOCKED. This document authorizes no market data run, deployment or trade.

1. Before reading outcomes, archive a producer-issued coherent historical manifest
   with immutable source digests, exchange/market/symbol/timeframe identity,
   availability, watermark, revision and horizon. Verify chronology and gaps at
   each origin. Reject unavailable/future/revised inputs. Record code/config SHA,
   seeds, universe membership and every attempted run, including failures.
2. Freeze train/validation/test dates, half-open label intervals and explicit
   embargo at least as long as justified dependencies. Reject label overlap across
   partitions. Fix the trained horizon and aligned windows before training.
3. Freeze held-out symbols; exclude them as training targets AND context tracks.
   Report seen and held-out instruments/timeframes separately; declare missing
   histories before scoring. Changes to the universe create a new experiment.
4. Train fresh models per fold. Freeze thresholds/hyperparameters using validation
   only before requesting test predictions. Independent holdout folds reject prior
   OOS reuse; deployment-style expanding retraining requires explicit sequential
   labeling and must never be reported as independent holdout evidence.
5. Use fixed-disjoint decision horizons; retain each prediction, label, scale,
   event identity, source digest, checkpoint digest, threshold and position.
   Report NLL, MAE, empirical coverage, standardized residual moments and
   reliability by instrument/timeframe/regime with sample counts. Coverage alone
   is not fitted calibration. Fit any recalibration only on validation, then freeze.
6. Compare zero, train mean, observed-return persistence, train-only ridge,
   randomized signals, shuffled training labels and strictly prior same-series
   delayed features with identical OOS timestamps. Record selection count and
   dependency-aware uncertainty. Current pooled moving-block CI is exploratory;
   it does not establish cross-instrument independence or adjusted significance.
7. Reconcile independent entry/exit fees, spread and slippage against an external
   ledger. Current code charges both legs and one flat nonnegative funding charge
   per horizon. Historical signed, side-aware funding at actual event times,
   latency/fills, leverage, margin and liquidation require a separate validated
   simulator before real portfolio profitability claims. Never pool overlapping
   multi-instrument notionals into a portfolio claim.
8. Refuse checkpoint overwrite/replay, replay saved predictions from the verified
   checkpoint and compare exact input/config/model identities. Archive reports,
   negative controls and cancellation/failure outcomes. Require an independent
   reviewer and all acceptance gates before changing BLOCKED status.

No dates, instruments, costs or success thresholds are invented here: those must
be frozen in the authorized dataset-specific manifest before accessing its OOS labels.
