# Grid → Strattester → ML mathematical contract (proposal v0.1.0)

Status: EXPERIMENTAL / NO LIVE TRADING. This document does not certify existing adapters.

## Provenance and immutable boundary
Grid must export a read-only, consistent snapshot with dataset_sha256, schema_version, snapshot_id, source_commit, market_type, venue, symbol, tick_size, quote/base units, event_time_ns, ingestion_time_ns, available_time_ns, watermark_ns, quality_status, eligible and gap_status. Timestamp fields are UTC Unix nanoseconds. Reject missing units, ambiguous timezone, duplicate event keys, negative volumes, inconsistent OHLC, stale snapshot or invalid watermark. Sort deterministically by (event_time_ns, source_sequence, unique_event_id); never rely on ingestion order. An observation is available to a prediction only if available_time_ns <= prediction_cutoff_ns AND its event-time interval is closed by the snapshot watermark.

## Mathematics
For positive close P[t], log return r[t] = log(P[t]/P[t-1]); simple return R[t] = P[t]/P[t-1]-1. Do not mix them. No return across unresolved gaps or incompatible contract adjustments. Rolling sample volatility uses sqrt(sum((r-mean(r))^2)/(n-1)), n>=2; annualization only with explicit sampling assumptions. Normalization parameters (mean/std, quantiles, winsorization, missingness) are fit on train only, versioned, and frozen on validation/test. Zero variance has an explicit deterministic policy.

## Temporal features and pair representations
Each feature records its full dependency interval and latest available_time. For prediction cutoff T, all dependencies must have available_time<=T. Pair z[i,j] records dependency union and is valid only when both members and every derived intermediate are available at T. Triangle/pair updates may propagate information through a third index k: mask every participating edge and its dependency closure, not just final attention logits. Causal attention permits keys j only if their full dependencies are available by query i cutoff; padding and missing-data masks compose with causal masks. No claim of equivalence to biological AlphaFold.

## Evaluation and integrity
Labels record [label_start_ns,label_end_ns] and execution horizon. Purged walk-forward removes overlapping label intervals across train/validation/test and applies embargo where required. Fees, slippage and funding are explicit. Store dataset SHA256, model SHA256, code commit, dependency lock, seed, hardware, precision, split boundaries, scaler state and feature schema. Compare baselines, shuffled-label negative control, instrument-level OOS metrics and uncertainty intervals. A test PASS is not proof of predictive efficacy.

## Independent verification matrix (required before acceptance)
1. Analytical identities: exp(log-return)-1 == simple-return within tolerance; constant series volatility zero; hand-calculated sample variance.
2. Property tests: no future perturbation may change past features/predictions; triangle updates and pair pathways included.
3. Time: out-of-order ingestion, duplicate event IDs, late arrivals, watermark regression, clock skew, open candle, daylight-saving transitions, gaps.
4. Snapshot: concurrent writer/read-only reader; stable snapshot hash; deterministic ordering; missing/ineligible rows fail closed.
5. Splits: adversarial overlapping labels, embargo, boundary conditions, train-only scaler fit; no cross-instrument leakage.
6. Numerical: float32/float64 CPU/GPU tolerance budgets; NaN/Inf and zero variance; deterministic seeds where supported.
7. Evidence: independently recompute metrics from frozen artifacts and verify SHA256, JUnit and JSONL receipts; report unsupported checks as NOT_RUN.

## Integration boundaries
Grid owns raw observation semantics; Strattester owns versioned feature/label transforms; ML owns fitted artifacts and inference cutoffs; math independently verifies equations and invariants. No live exchange orders, no production database mutation, no automatic deployment. Release gate remains NO-GO until real schema and adapters have been inspected and tests executed against pinned commits.

## Source-semantics and license guard (audit addendum)
Grid's documented `candles_1m` and `footprint_1m` describe **executed public trade flow** (aggressive buy/sell volume, delta, executed-volume POC). They must never be renamed or interpreted as resting order-book depth, bid/ask queue size, or true liquidity. The README is descriptive evidence, not verification of physical PostgreSQL DDL; the actual schema, revision, constraints, tick scaling and timestamp types remain UNVERIFIED.

The `math` repository's README states that no license is granted by default. Until explicit authorization and pinned-source review, do not copy its implementation into Strattester. Independently derive standard equations and compare results through isolated, read-only test fixtures. Its documented Bitcoin/polynomial-root example is illustrative and is not evidence of forecasting power.

## Explicit remaining acceptance blockers
- Obtain exact Grid DDL and query/adapter paths at a pinned commit; verify UTC timestamps, watermark, snapshot consistency and all market/instrument keys against code and synthetic PostgreSQL fixtures.
- Verify Strattester's actual feature builder and Evoformer-like pair/triangle update call graph; this reference mask is a **predicate**, not enforcement inside model kernels. Require perturb-future metamorphic tests at every intermediate layer.
- Validate independent `math` equations, licensing and numeric tolerances against frozen inputs; compare CPU/GPU precision, reject nonfinite intermediate tensors.
- Require both general CI and mathematical CI at the exact PR HEAD, including nonzero collected test count and immutable test evidence. Do not promote README-level assumptions to VERIFIED.
