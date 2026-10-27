# Offline ML/OOS/funding engineering

This branch extends the PR21 research harness. It never admits real OOS,
funding history, G1 or trading. See [real OOS protocol](financial-real-oos-protocol.md).

`run_experiment` trains multiple target instruments/timeframes with fresh
structural models; horizon remains fixed by model configuration. A symbol
holdout excludes that symbol across venues/markets from training and validation
selection targets/context. `validation_count` now counts only selection rows.
Every fold records its training instruments, input/model hashes, seed and config.
Walk-forward retains explicit embargo, interval purge, nonoverlapping test windows
and prior-OOS reuse policy. SEQUENTIAL_RETRAINING is never independent holdout.

Validation alone fits a bounded Gaussian scale MLE (multiplier 0.05–20) and each
strategy's threshold from the fixed grid 0/0.0005/0.001/0.002. Raw Gaussian scores
remain `test_metrics`; `calibrated_test_metrics` uses the recorded calibration
without changing model weights. The bound is an engineering regularizer, not
evidence of market calibration. Zero/mean/persistence/ridge and random-signal,
shuffled-training-label and delayed-same-series controls each report MAE and
their own validation-selected threshold and round-trip cost ledger.

## Explicit synthetic funding bundle

Existing `walk-forward` arguments remain required. Add BOTH
`--funding-bundle <bundle.json> --funding-bundle-sha256 <independent SHA256>`
to opt into signed synthetic settlement scoring. Without them funding remains
BLOCKED/excluded. No automatic runtime funding source is enabled.

Bundle schema is exactly:

```json
{"version":1,"scope":"SYNTHETIC_ENGINEERING_ONLY","entries":[{
  "path":"funding.json","sha256":"<external funding SHA256>",
  "policy_path":"policy.json","policy_sha256":"<external policy SHA256>",
  "trust_store_path":"trust.json","trust_store_sha256":"<external trust SHA256>"
}]}
```

All paths are bundle-relative safe files. Each policy is the existing pinned
`FundingPolicy` exact version-1 object. It selects one exact exchange/market/
symbol/timeframe, producer/source/build/schema/snapshot/epoch, coverage and trusted
verification cutoff. Maximum 64 entries, 256KiB bundle and 10000 total retained
events. Policies/manifests/trust are independently pinned through the bundle;
signatures use the existing independently pinned OpenSSL verifier. Every example
partition needs one window; duplicate/missing/extra/aliased markets fail closed.
Signed epoch equality establishes synthetic consistency only. Coverage of each
scored interval (including flat decisions) is checked by the ledger.

Funding is post-hoc test scoring only. Both model and ALL control scorecards
retain the funding-excluded `ledger` and separately add `funding_adjusted_ledger`.
Rows expose gross return, fee cost, slippage cost, signed funding cashflow,
turnover and net return. Round trips use unit entry notional, pay both entry and
exit costs and liquidate every horizon. Funding uses `(entry,exit]` with positive
bps charged to longs and credited to shorts. Do not sum overlapping timeframe
sleeves into portfolio wealth. A valid signature never proves retained historical
truth/completeness or execution fills.

## CPU synthetic E2E

From a clean checkout with dev and CPU research dependencies:

```text
python scripts/ml_oos_synthetic_e2e.py --output <new-task-owned-directory>
```

The harness creates public RFC8032 signed synthetic price/funding inputs for 3
instruments and 2 timeframes, trains two fresh folds with a held-out instrument,
records calibration and all controls, checks literal cashflow arithmetic and
verifies 36 forecasts in another Python process. The child re-verifies signed
source exports and externally pinned checkpoints/report, reproduces predictions
and raw/calibrated scores, and inspects model-only recovery. Python socket denial
is a software test guard, not OS egress isolation. SHA256SUMS covers every fixture,
checkpoint, report and evidence.json; evidence names the exact clean HEAD/tree.
Artifacts contain public test seeds, never producer/owner secrets. Output location
and runtime information are recorded, so package bytes differ across hosts even
when trained checkpoint/prediction contents agree.

`inspect_checkpoint_recovery` is read-only and requires external checkpoint,
training-dataset and seed pins. Version 1 lacks optimizer state: deterministic
restart is supported; optimizer continuation is not. Private fold staging avoids
publishing early checkpoints when a later fit fails. OS failure during exclusive
publication may leave unregistered finals; crashes may leave staging orphans.
Never auto-adopt or overwrite those files. Restart into a fresh run directory;
physical durability and hostile namespace races remain unqualified.

## Validation and review disposition

New tests cover literal calibration/cost arithmetic, future/test-label isolation,
held-out validation-label isolation, funded baselines/controls, modified checkpoint
rejection in a fresh process, late-fold failure/restart and independently pinned
recovery without orphan mutation. New nodes are mandatory in the existing
training/integration gate manifest. `ml-oos-synthetic` additionally publishes
JUnit/raw JSON and E2E SHA256 evidence on exact PR head_sha. Existing external
system acceptance intentionally stays BLOCKED.

Independent review reproduced three P2 issues during implementation: held-out
validation labels affected calibration; baseline funding comparisons were absent;
fresh-process smoke only loaded weights. Each received a RED regression before
the fix. Full-suite testing also caught missing calibration in the standalone
runtime allowlist; packaged isolated-import/experiment coverage exercises the fix.

P0: no newly confirmed finding. P1 external blockers: authentic coherent price/
funding/outcome history, one-use real OOS admission/registry, qualified physical
crash persistence, GPU/full upstream parity, G1 authorization. P2 fixed: the
review findings above, late-fold partial publication on fit failure and runtime
dependency omission. P2 residual limitations: unit-notional float accounting,
bounded validation calibration on small samples, no optimizer continuation and
no atomic multi-file commit under OS publication failure. These are disclosed
boundaries; software evidence does not satisfy the external P1 gates.
