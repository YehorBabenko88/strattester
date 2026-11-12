# MWI offline research harness

Standalone research module for synthetic level breakout/bounce/timeout probabilities. The baseline imports no Grid, Strattester runtime, database, provider, scheduler or ledger. The separate stage2 finite-cycle CLI binds only the explicitly approved, exact-byte-pinned existing Strattester pure OHLC simulator in a new private namespace. It does not submit runtime jobs, export data, place orders, promote models or deploy anything.

`MWI_OFFLINE_RESEARCH_READY` means the bounded synthetic protocol and local file interfaces work reproducibly. Real market predictive value, historical source authenticity and native training admission remain blocked. Graph features are deterministic summaries; no GNN, Transformer, RL or MuZero implementation is claimed.

## Run

Use an existing Python 3.12 interpreter; no packages to install:

```
python -I -S -B run_tests.py
python -I -S -B run_research.py --output NEW_RESULT_DIRECTORY --source-head EXACT_40_HEX_SOURCE_CONTEXT --bars 6000
```

The output directory must not exist; its parent must exist. `--source-head` is a caller-pinned source context, not source authentication. Results also bind every module's actual SHA256; when packaged into an owner repository report its exact implementation commit separately. Do not invent a Git SHA for this standalone bundle.

The run creates a canonical synthetic dataset with externally reusable manifest pin, result, resource observation and stage checkpoint. The source-fixed protocol uses three expanding development folds, separate calibration blocks and a final20% calendar-time holdout. Full horizon purge and an additional12-minute embargo protect fitting/calibration boundaries. Model scaling/weights fit on train only; temperature .5/1/2 is selected solely on calibration. The final holdout is internal to a synthetic development artifact; it is not independently externally sealed market OOS.

To consume exactly the same synthetic bytes read-only:

```
python -I -S -B run_research.py --output ANOTHER_NEW_DIRECTORY --source-head SAME_SOURCE_CONTEXT --snapshot EXISTING_RESULT_DIRECTORY/dataset --manifest-sha256 EXTERNALLY_RECORDED_MANIFEST_SHA256
```

No source file is modified. A manifest hash supplied by the same untrusted artifact does not authenticate that source. The normalized adapter is synthetic-only and requires explicit synthetic opt-in internally. It validates schema, source pin, dataset ID, raw byte hashes/sizes/counts, temporal order/coverage/units, finite OHLCV, missingness, strict membership and linked path refusal. It rejects historical training input until owner provenance/admission is separately implemented. It does not claim atomic defense against a hostile concurrently changing filesystem.

## Future snapshot read path

```
python -I -S -B inspect_snapshot.py --file OWNER_SUPPLIED_GRID_HISTORY_V11_JSON --sha256 EXTERNAL_FILE_SHA256 --source-head EXPECTED_PRODUCER_HEAD
```

The inspector accepts only the exact inspected Grid history v1.1 envelope. It verifies external file bytes, native content/envelope identities, integer-ms clocks, minute-exclusive boundaries, availability/watermark order, receipt-hash bindings, source/market units and bounded continuous coverage. It returns facts only, with training_eligible=false even for HISTORICAL input. Receipt contents/authenticity, historical truth and source-owner admission cannot be inferred from hashes. No normalized training data or fake receipts are created. A missing/incompatible native schema is refused; no PostgreSQL, network or automatic export fallback exists. Strattester sealed financial snapshots remain a separately pending adapter with explicit ns/revision/coherence semantics.

When ROOT supplies a separately approved snapshot, run file integrity/schema/coverage/availability discovery first and update the P0 JSON reports. Only after owner-approved provenance and decision-time adapter may real data enter existing Grid/Strattester training paths. This module is not that admission path.

## Experiment semantics

Fixed scenario: continuous artificial oscillation/noise/plateau regimes, seed20261112,6000 one-minute TOYUSDT bars. No empirical market calibration. TOY_NEAR_ZONE_V2 freezes support/resistance extrema, ATR and graph from48 available prior bars before the touch opens. Touch range must intersect the narrow zone; close must remain inside the broader outer barriers. This near-zone cohort differs from the earlier stricter within-zone proposal; the version and deviation are explicit. Same-instrument episodes are suppressed through the12-bar horizon, including rejected ambiguous episodes. Labels are directional first passage only on full bars starting after decision availability, and mature after all horizon observations become available. Ambiguous/gapped/pending outcomes are counted, not relabeled as bounce.

Baseline8 features, node-only11 and graph13 use identical examples. Graph adds nearest-level/confluence/node-count statistics and nearest-price-edge degree/distance summaries from48 prior nodes. Node-only contains the same node summaries without edges. This is a descriptive topology ablation, not proof of market causality. Negative controls circularly displace labels with a nonidentity check (constant labels are UNINFORMATIVE) and permute only edge summaries while preserving node-only columns. Control deterioration is reported, not assumed or used to choose a winning model.

Metrics include multiclass Brier sum, log loss, top-label ECE/reliability bins, class counts, uncalibrated/calibrated scores, and paired exploratory circular-block bootstrap intervals at3/6 episodes. These dependent small synthetic cohorts do not support a market significance claim. No confirmatory p-values or multiple-testing-adjusted discovery is claimed; subsequent exploratory changes require fresh real OOS. Tiny minority classes make calibration estimates unstable. No PnL/fill/cost simulator result follows from classification scores.

Limits:10000 bars,256 examples,64 features maximum, fixed100 fit epochs, serial one process, GPU0. Measured run resources are separate from reproducible metrics. The60-second bound is a checked postcondition, not an OS hard quota. Checkpoint is a stage/integrity record, not resumable model state. Existing owner checkpoints/leases remain the future integration mechanism.

## Review and ownership

RED/GREEN evidence, independent review/fixes and final verification are under evidence/. One Windows symlink test may skip when privileges prohibit fixture creation; report it rather than treating it as exercised. No native/physical/hosted-CI qualification follows.

Proposed owner scope: Strattester research/mwi_offline/** plus docs/research/MWI_OFFLINE.md. ROOT and A7 explicitly approved this new source-only namespace on base37ff7e9d12a4d2dccd788fc493c28557dbe8bcea; all75 open PR file lists were checked for path overlap. No shared contract or runtime file changes are included, and no merge/deployment is authorized.

## Stage2 finite synthetic strategy feedback

Root/A7 additionally approved a new isolated branch fromPR81 and the NEW contained CI workflow only. Existing workflows/core/package/config/ResearchRunner/sync/store remain unchanged. This stage is not MWI_RESEARCH_ENGINE_COMPLETE.

```
python -I -S -B run_engine_guarded.py --output NEW_CYCLE_DIRECTORY --source-head EXACT_CODE_CONTEXT
python -I -S -B run_engine_guarded.py --output SAME_CYCLE_DIRECTORY --source-head SAME_CODE_CONTEXT --resume
```

The guard launches one fixed isolated child and stops it on a60-second timeout (parent+research child, no CPU hard-quota claim). Source4200 plus fresh synthetic policy holdout1800 bars, at most10000 total bars/256 total examples,6 evaluated declarative candidates and2 versions. A finite invocation is not a scheduler, recurring controller, storage service, model registry service or replacement ML backend.

Strategy objects have exact versioned schemas, dataset/model-bundle hashes, required features, confidence thresholds, explicit stops/targets/horizon, fixed virtualcapital/position/risk/drawdown limits and frozen cost assumptions. No arbitrary code, live mode or promotion is accepted. WAIT and bounce-rule controls precede baseline-probability and graph-probability candidates. Only development profit can request prespecified stricter threshold versions. All negative/rejected/cost-stressed results remain immutable artifacts. Existing final OOS is not accessed for selection. The selected strategy is frozen before a separate fixed-seed20261113 synthetic realization begins after the source calendar window. This is a prospective synthetic policy test, not empirical market OOS; no statistical economic edge is claimed.

Development split boundaries come from the source calendar, not outcome eligibility. A future-value mutation test verifies earlier fitted models/IDs remain identical. Models/scalers/calibration parameters and all candidate/result IDs are serialized as immutable local artifacts. Production Grid registry/lifecycle and Math transformations are NOT connected; local artifacts do not inherit their authority.

The simulator source closure is exactly3 files at the reviewed original Git blobs: version-only package init, empty research init, execution.py. Exact RAW SHA256 execution99c1a3a7907b0481c0f2a4f239fb6808f137834b39fffaf7885ef60f66246832 is required; Windows CRLF423aa0... is explicitly rejected, even if normalization would match. A NEW private capsule is populated from Git HEAD raw blob bytes and verified before any import. Existing checkout files and Git configuration are never rewritten. Module/package origins, isolated stdlib profile and all3 raw pins are checked, including before/after each call. Inputs are owned builtins; callbacks/arbitrary iterables/nonfinite data/invalid OHLC or policies are rejected. Metadata is frozen/copied. The existing simulator alone determines fills/exits/PnL.

Scenarios use conservative SL_FIRST, explicit5.5bps fee and2bps adverse slippage, one-bar latency, fixed100 notional/1000 initialcapital. Stress uses10bps fee/8bps slippage. Funding is explicitly a synthetic-zero assumption, not observed absence. Depth/queue/actual fills/partial fills/MFE-MAE intrabar paths are unavailable. Drawdown is closed-trade equity, not an intrabar loss guarantee. Ex-ante risk bounds cannot eliminate gap loss. No financial/live/trusted/native runtime qualification follows.

Checkpoint updates use same-directory tempfile+fsync+atomic replace. Resume checks source/config/dataset identity, closed artifact membership, every bounded byte hash, required model/selection/holdout/result artifacts and result identity. A removed pin cannot bypass checking. Ordinary interrupted simulation is retained and reproducibly resumed. A crash between artifact write and checkpoint publication leaves an orphan and **refuses resume**; no automatic orphan adoption, full power-loss transaction recovery, distributed fencing or hostile coordinated tamper resistance is claimed. Checkpoints are unsigned local stage receipts, never source authenticity or execution admission.

Contained hosted CI uses pinned checkout/setup-python commits, Python3.12 Ubuntu/Windows, contents:read and the fixed isolated test CLI. Process-scoped Git config requests exact LF checkout; existing mandatory workflows are unchanged. Local/hosted/native/real-data qualifications remain separate. Full engine completion is blocked on admitted historical datasets, Math/Unified/Terminan owner contracts, Grid registry/training integration, execution fidelity, independent market OOS and A8 acceptance. Self-supervised/temporal/boosted/GNN/RL task readiness must not be inferred from this synthetic loop.
# Stage3 cross-repository preparation

The isolated Stage3 modules add read-only Math feature envelopes, bounded Grid ML preparation metadata, Unified compatibility preparation and a Learning Lab result-file reader. They import no owner runtime and submit no jobs. Exact-source ownership is separate from execution/admission. Math remains EXECUTION_BLOCKED; Grid/Unified native interfaces are not accepted for MWI. Three-class MWI targets are refused by the inspected binary/regression Grid seam; TIMEOUT is never dropped or renamed.

`controlled_search.prepare_search` validates the existing declarative strategy format, caps six declarations/two versions, deduplicates semantics while retaining lineage, and records validation/duplicate/budget refusals. Noncanonical or unbounded input is refused before batch identity. The existing finite `feedback.run_cycle` now admits each initial/next-version batch through this function and saves search decisions in the existing immutable checkpoint inventory. Completed resume requires these artifacts. Existing simulator, model fitting, disjoint calibration, frozen synthetic holdout, cost stress, WAIT policy and failure retention remain in use. Model-level negative controls remain the existing contained evaluation workflow; no new orchestrator/ledger/promotion path is introduced.

`snapshot_readiness.inspect_snapshot_bundle` composes the existing Grid v1.1 file inspector with a strictly local proposed sidecar. It verifies dataset/raw identities and bounded local evidence-reference hashes, not receipt authenticity. Source-owner approval and external admission need actual owner verifiers; all real-data training remains BLOCKED. OHLCV presence is never upgraded into L2/trades/footprint/OI/funding coverage.

After freezing selection, the finite cycle also saves one fixed development-only circular-forecast-reassignment control, with at most two base/stress cost scenarios and no retraining or holdout access. WAIT/rule policies or unchanged reassignment produce CONTROL_UNINFORMATIVE with null metrics. This exploratory diagnostic is not significance evidence. Control failures are retained and rethrown; completed resume requires the control artifact. Six search candidates and one fixed diagnostic policy are separate explicit bounds. The existing external60s guard remains a wall timeout, not a hard CPU/RAM quota.

Learning Lab proposal, bounded synthetic fixture, exact source/result pins and limitations are documented in `docs/mwi/learning-lab-readonly.PROPOSAL.md`. Unknown progress/probabilities/graph payloads remain explicit. Local contract tests are not A8 acceptance or native compatibility.
