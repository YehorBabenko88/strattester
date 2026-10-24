# Implementation notes and acceptance boundaries

Owner approval: PR21 comment 6385378621, 2026-10-24; approved design HEAD 9778e79cb3dbe49b9e88dccb05acf2286374a87a. Source PR15–20 heads rechecked unchanged before implementation. The branch remains Draft and never enables trading.

## Milestones

- Import: `572d17d7df6799f9d2fc1145d21e23c998924d4e`, 72 audited source paths with per-file source HEAD/blob map. No merge or cherry-pick of the agents' branch histories.
- Immediate AF-002/AF-003 fixes: `101b133` (full SHA available in git history): strict integer timestamps and OPM track/outer/parameter/byte admission. Regressions first failed as expected (six failures, one preexisting pass), then 14 selected tests passed.
- Data/math boundary: `cf081b9f2ac6fd584f4f726654451801cd1eff86`, normalized read-only SQLite reader, immutable bounded/hash-verified JSON snapshot, strict causal/revision/quality/provenance/coherence contract. Real Strattester DDL is rejected rather than enriched with invented ingestion history. Selected tests: 37 passed, four subtests; full local imported+contract suite: 711 passed, four skipped, 18 subtests.
- Connected model / AF-001 and CPU coverage / AF-004: `6468a7b95cdd5f31cbff17a0afea5ae2041dc102`; pair-biased row, column, MSA transition, OPM, triangle multiplication/attention, pair transition, target single representation and recycling feed the Gaussian head. Main model remains separately named from the original heuristic. Initial references/model tests: 21 passed. CPU gate subsequently passed 72 tests without skips; two explicitly GPU cases deselected by the legacy CPU script. New financial gates use exact node lists instead of deselection.

The cf081b9 core PR run 40103075399 failed because a newly mandatory test imported torch while core CI did not install it. CPU run 40103075372 and math run 40103075378 passed. Core dependency installation was corrected. Local CPU script's first expanded run hit the previously diagnosed system pytest temp-directory ACL; an owned --basetemp fixed it. Neither failure is reported as passing evidence.

## Financial model semantics

One model call predicts ONE explicit origin, not a sequence of online per-position forecasts. All history tracks must be available by that origin; masked values are zeroed before projections and cannot enter OPM, triangles or recycling. Track zero is the named target instrument; context tracks retain same-time alignment. Feature construction selects an explicit timeframe and refuses missing/misaligned windows rather than padding data implicitly. Three input channels are available return, trailing mean and trailing population volatility; these fixed causal features do not fit normalization on evaluation data.

The output is Gaussian log-return mu and scale, with scale in [1e-5,10]. Prediction contains exchange/market/symbol, origin, caller-recorded availability, horizon, dataset SHA and model SHA. Gaussian fit/calibration is exploratory, not a validated financial law. A target-track regression found and corrected an initial symmetric pooling error: swapping the target must change its forecast.

The fixed trained horizon is StructuralConfig.horizon_ns (default 120 ns for toy engineering fixtures; production experiments must explicitly set the real horizon in ns). Different input timeframes may share that duration, but labels/predictions cannot silently change it. Verified checkpoint identity and current config/tensor fingerprint are rechecked before typed inference. Instrument holdout excludes both labels and all training context tracks. CPU float32/float64 compute is admitted; safe checkpoint inference requires CPU float32. GPU/half paths are not accepted by this candidate.

## Numerical mechanisms and provenance

Independent implementations reference AlphaFold modules.py at c77e5d2a8961d1a353632c462914ff0a32a950f6. No upstream executable code, weights or atom output is incorporated into forecasting. Preserve Apache-2.0 attribution for any later copied implementation. Current tests include explicit-index OPM/triangle/column attention, row mask invariance, attention orientation, finite gradients, connected operator hooks, zero/missing masks, recycling and origin-availability perturbation. Full upstream-equivalence acceptance remains BLOCKED pending complete independent reference evidence; selected adaptations are not branded original AlphaFold inference.

math at ccfe97dd88b1ebee9bd19795002a30d0bd1c1ca3 has only README. PR18's standard-library oracle plus an independently derived Decimal log-return and literal variance check are retained as local reference tests, never claimed to be executable math-repository code.

## Training, checkpoint and evaluation

Training is deterministic, bounded and cancellable; any failure restores the pre-fit state and does not implicitly create a checkpoint. Tensor-only JSON checkpoints validate caller-pinned SHA, byte size, exact config/names/shapes/finite values and are atomically published without overwrite using a same-directory temporary file and exclusive hard-link. No pickle, torch.load, arbitrary imports or executable artifact is used. Replaying an existing checkpoint path fails; read-only inference can explicitly reload it.

The engineering experiment covers multi-instrument/multi-timeframe windows, an instrument holdout, chronological purged train/validation/test, embargo, train-only baseline fits, validation-frozen thresholds, random signal/label shuffle/delayed feature controls, entry/exit costs, terminal liquidation, distribution scores and exploratory bootstrap interval. Snapshot/label hashes and training-only dataset hash are separate. A simple per-horizon cash-return ledger is not a leveraged portfolio or exchange fill simulator. Funding can be specified explicitly per horizon but no exchange schedule is invented. Real OOS remains BLOCKED; in-memory experiment results are always labelled SYNTHETIC_ENGINEERING_ONLY.

## Evidence and CI

financial-integration.yml checks out the exact PR head (not a synthetic merge), executes seven separately reported gates, then always aggregates expected artifacts. Required exact test IDs and minimum counts are reviewed in scripts/financial-gate-manifest.json. Missing dependency/test/report, critical skip/xfail/xpass, stale SHA, dirty checkout or unsuccessful workflow result cannot pass. CPU manifest exclusions list only two GPU tests and the Linux-inapplicable Windows lifecycle test; lifecycle is still exercised by the existing Windows core matrix. Windows lacking symlink privilege blocks the local data/security gate; hosted Linux must actually execute those tests.

Full system acceptance deliberately fails closed with BLOCKED external real_oos, gpu and full_upstream_equivalence requirements. A failed acceptance job is expected until those evidence gaps are resolved; engineering job results remain separately visible. No runner or dataset attestation is fabricated to make this job green. Avoid duplicate push/PR core runs on the integration branch; concurrency cancels superseded runs on the same workflow/PR, retaining latest-HEAD artifacts.

Grid's real producer/MVCC/cross-source coherent snapshot is an additional explicit BLOCKED external requirement (grid_coherent_snapshot). Passing normalized fixture data tests is not production Grid synchronization evidence. Structural walk-forward is executable through run_walk_forward, including preflight of every temporal window, fresh fold checkpoints, explicit prior-OOS reuse policy, and retained split/cost/holdout/training configuration. Overlapping windows and unauthorized OOS reuse are rejected before checkpoint-directory creation. A hand-count correction in the two-fold test includes the second interval's 5400 boundary, giving 12 and 16 test cases respectively.

## Rulings and limits

- Existing task-isolated clone on integration branch is sufficient; no extra worktree. Wrong choice would risk shared local state, but no agent source branch is checked out for writing.
- Tensor JSON is the initial safe checkpoint format; costs disk/parse space compared with a binary format, bounded by the loader's size and model limits.
- Qualify imported research math test imports to match the inherited pytest import mode; affects test discovery only.
- Require explicit coherent export and producer trust at the snapshot boundary; matching wall-clock cutoffs cannot establish cross-source atomicity. Without trustworthy historical availability the data gate stays externally BLOCKED.
- Gaussian distribution and per-horizon cost ledger are initial research choices approved by design, not profitability assumptions. Real-data execution/fill/calendar validation is still required before acceptance.
