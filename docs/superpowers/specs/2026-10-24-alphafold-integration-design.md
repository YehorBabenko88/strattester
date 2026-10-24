# Financial structural research integration — proposed design

Status: proposed for review; implementation not started. The audit and evidence collection are separate from product implementation.

## Intent and constraints

Build an offline research pipeline on one pinned integration HEAD: Grid -> immutable snapshot -> financial adapter -> structural model -> typed prediction -> independent evaluation. Preserve the five agents' branches, use integration/alphafold-financial-system and a Draft PR, never merge main, trade, mutate production databases, execute untrusted weights, or equate a simplified financial backend with original AlphaFold. All required acceptance gates fail closed.

## Approaches

The task requires retaining the original mechanisms and real integration evidence. A biological AlphaFold runtime would introduce atom/sequence-specific outputs and an incompatible heavy environment without financial semantics. Keeping only the current heuristic financial model would fail the mechanism requirement. The proposed approach is a separately named PyTorch financial structural model using independently verified adaptations, with upstream AlphaFold pinned as reference and source attribution. This follows the user's required mechanism mapping while retaining honest limitations. No biological weights are used.

## Component import and ownership

Use PR16 as the source for PR15 geometry and standalone operators; use PR20's hardened versions of the nine divergent paths; import PR17 data guards, PR18 independent reference functions, and PR19 evaluation/baseline components only after compatibility review. Record original PR/head/path for each imported change. Do not mass cherry-pick or merge source histories. Keep existing simplified model explicitly experimental and separate from the new connected model. Place contracts, model, training and acceptance code in focused research modules rather than production runtime paths.

## Snapshot and time contract

Contract v1 requires exchange, market_type, symbol, timeframe_ns, candle_open_ns, candle_close_ns, event_ns, ingest_ns, available_ns, watermark_ns, quality, eligible, complete, revision, producer/source commit, snapshot/coherence identity and dataset SHA256. Timestamps are non-boolean integers with named units; explicit conversion functions reject precision loss. Identical symbols from different markets are distinct keys. Availability must be no later than prediction origin; candle must be closed and covered by the source watermark. Labels may use later outcomes only in a separate evaluation partition.

Production adapters are read-only. Never call SQLiteMarketStore.open or ShardedMarketStore constructors from research reads. A single SQLite file uses mode=ro, query_only and an explicit read transaction; producer-authenticated immutable exports are preferred. Separate mutable SQLite shards or PostgreSQL plus SQLite require a producer-issued coherent export/epoch. Matching cutoff numbers alone cannot prove consistency. Missing, mismatched, incomplete or revising sources produce BLOCKED and no dataset. Existing tables lack enough history to reconstruct ingestion/revision availability; do not invent it.

Hash canonical bytes of the full ordered records plus schema/provenance manifest; verify file identity/size and bind the opened object to the hash used downstream. SHA256 detects content changes, not trust in the producer. Accept only locally verified artifacts from an explicit trusted experiment registry. No pickle, biological weights or arbitrary object deserialization.

## Model and financial semantics

Proposed financial axis choices: N is historical closed-bar position and S is a declared aligned instrument/feature track at the same position. These are engineering choices requiring causal alignment tests, not biological MSA equivalence. No future segment enters any track. Start with small configurable dimensions and strict byte/parameter budgets. Operators include pair-biased row attention, column attention across available tracks, MSA transition, OPM, outgoing/incoming triangle multiplication, starting/ending attention, pair transition, residual/normalization/masking, single extraction and bounded recycling. Preserve a complete dependency mask through all contractions and recycling. A causal row mask alone does not fix a future-contaminated pair representation.

Predict a Gaussian distribution over horizon log return (mu and positive bounded scale), with explicit origin_ns, available_ns, horizon_ns, instrument identity, dataset SHA and model SHA. This is a proposed initial family, not a claim of calibrated financial returns. Compare its likelihood and calibration to baselines; financial volatility targets and variance estimators are documented separately. No structure module for protein atoms is used as a forecast.

Before creating parameters or expanded tensors, admit batch, tracks, tokens, channels, head count, depth, recycle count, dtype bytes, parameter/activation/backward storage and attention cubic workspace. Reject empty/invalid dimensions, NaN/Inf and unsupported dtype/device combinations. Admission is a conservative bound; host and device OOM still need controlled handling. Cancellation is checked between bounded steps and saves only a complete verified artifact; failed jobs never register partial output.

## Training and evaluation

Fit transforms on training only. Chronological purged walk-forward with label-overlap checks, explicit embargo and instrument holdout; deterministic seeds and versioned full configuration. Use zero, mean, persistence and linear baselines, label shuffle/delayed-feature/random-signal controls. Prove optimizer updates meaningful parameters, then reload a bounded, verified tensor-only artifact in a fresh process and reproduce inference. Record framework/runtime versions and dataset/model SHA256.

Evaluation uses a documented ledger and units; do not treat position-weighted log returns as a fully realized cash PnL simulator. Account for entry/exit turnover, terminal liquidation, fees/slippage and market-specific costs. Report distribution loss/calibration, cost sensitivity, block-bootstrap intervals, sample counts and OOS baseline comparisons without declaring success from synthetic data. No real data is available in the pinned source trees; real OOS gate remains BLOCKED until a coherent export is provided.

## CI and acceptance

Separate core, data/concurrency, mathematical reference, PyTorch CPU, training/backtesting, adversarial and end-to-end jobs. Each gate publishes JUnit/structured accounting with source/integration HEAD, collected/executed/skipped/failed counts and required node IDs. Missing torch, missing required tests, critical skips or artifacts, stale SHA and test deselection fail the relevant gate. Always-run aggregator checks that every mandatory result is PASS on the same integration HEAD; workflow success is not sufficient evidence.

GPU is explicitly BLOCKED unless an executable supported GPU runner performs the selected tests, including finite gradients, bounded allocation, cancellation and controlled OOM. Local P400 inventory alone is not a runnable environment. Never assign a GPU label merely to make a job appear green. No current registered self-hosted runners were found.

Use read-only workflow permissions, nonpersistent checkout credentials, bounded timeouts and per-branch concurrency. Avoid duplicate push and PR runs, retaining completed evidence for latest HEAD. Offline tests deny socket/network/order submission and production paths; fixtures live under temporary work directories. End-to-end fixture uses actual pinned source DDL with a concurrent writer, and refuses unsupported source histories rather than filling absent fields.

## Validation milestones and external blockers

1. Import reviewed components with origin map; run unit suites on the combined tree.
2. Strict contracts, source-schema mismatch/epoch rejection and independent numerical references.
3. Connected model with hooks, gradients, causality and parameter/resource admission.
4. Deterministic fit/checkpoint roundtrip, baseline/control ledger and cancellation tests.
5. Mandatory gates and same-HEAD evidence registry; adversarial/offline E2E tests.
6. Real historical multi-instrument/timeframe OOS run and supported GPU execution, when actual inputs/environment exist.

The math repository currently supplies no executable oracle. An independently authored reference may satisfy the independent mathematical gate after equation-level and numerical verification, with explicit origin and double/decimal precision checks. It cannot be labelled verification against missing math code; provenance records must distinguish these claims. This follows the user's requirement for independent mathematical verification rather than inventing an upstream implementation. Historical producer identity/availability and cross-source coherent export cannot be inferred or restored by changing the reader. Data and OOS gates stay BLOCKED until actual evidence exists.

A tested Draft PR with blocked external gates is an intermediate deliverable, not completion of the user's system acceptance. Final acceptance waits for real historical OOS and supported GPU execution when GPU is required. No stage report may turn those conditions into optional warnings. These interpretations resolve the independent builder check's two questions without weakening the supplied acceptance rule.

## Review result sought

Approve or correct the proposed financial track semantics, Gaussian horizon output, conservative coherent-export policy and component import strategy before implementation. Trading remains NO-GO regardless of research test results.
