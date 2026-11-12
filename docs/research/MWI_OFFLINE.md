# MWI offline research harness

Standalone research module for synthetic level breakout/bounce/timeout probabilities. It imports no Grid, Strattester runtime, database, provider, scheduler or ledger. It does not submit jobs, export data, place orders, promote models or deploy anything.

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
