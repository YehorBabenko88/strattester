# Real OOS protocol — blocked until external evidence

Status: **NOT_EXECUTED / NO-GO**. Synthetic data and CI are engineering tests, not market performance.

## Required immutable inputs
1. Producer-issued historical snapshot with instrument/exchange/market-type/timeframe identity, coherent epoch, source revision, event time, ingestion time and first-available time.
2. Signed or independently authenticated funding events with producer, epoch, event timestamp, availability timestamp and full instrument identity. An HMAC verifies bytes only if the verification key is independently trusted and never taken from the same untrusted artifact.
3. Fees by market tier and effective date; order-book spread, liquidity, fill latency and slippage evidence. Reject missing evidence rather than substitute zero.
4. Precommitted universe, horizons, folds, feature definitions, seeds, model version, hyperparameter grid, benchmark set, correction policy and acceptance criteria.

## Protocol
- Pin source commit/tree, dataset bytes SHA256, authenticated funding canonical SHA256 and model artifact SHA256. Store the expected hashes outside the evaluated artifact.
- Construct features strictly from revisions available at each decision; use producer availability, not only candle close.
- Purge overlapping labels across instruments and timeframes; embargo fold boundaries; freeze held-out instruments/timeframes before training.
- Fit normalization and every model on train only. Select architecture, stopping and thresholds only on validation. Never use test for tuning.
- Distinguish independent holdout from explicitly labeled sequential retraining. Do not pool overlapping OOS returns.
- Evaluate zero/mean/persistence/ridge, label-shuffle, delayed-feature and random-signal controls under identical cost assumptions.
- Evaluate Gaussian NLL, calibration by instrument/timeframe/regime, directional accuracy, realized volatility error, confidence intervals with dependence-aware blocks, and multiplicity adjustment.
- Reconstruct every trade and funding event with signed cashflows, entry/exit fees, spread, slippage, turnover, terminal liquidation, exposure and capital accounting.
- Require negative controls to behave as expected; preserve all failed/negative evidence.
- Independently replay the model checkpoint and ledger from pinned immutable bytes in a fresh process.
- Release an OOS report only with raw trades, predictions, model/dataset digests, provenance, source revision and all CI job IDs.

## Stop conditions
Any unknown feature revision/availability, missing funding interval, inconsistent epoch, overlapping OOS, checkpoint mismatch, incomplete fills, unexpected skip or unverifiable source => BLOCKED.

No live trading, production database mutation, physical deployment or merge is authorized by this protocol.
