# Causal feature implementation evidence

Scope: owned files mwi_offline/synthetic.py, mwi_offline/features.py, tests/test_features.py and evidence/features-* only. No repository/service/provider/DB imports or edits. Stdlib-only standalone synthetic research, no admission or execution authority. Existing evaluation/adapter/run files were not edited.

## Observed TDD sequence

- features-red.txt: actual first test invocation failed because mwi_offline.synthetic did not yet exist.
- features-green-attempt1.txt: first implementation exposed invalid OHLC fixture values and a wrongly constructed timeout fixture. Fixtures were corrected to valid OHLC crossing the intended barriers; validation was not weakened.
- features-green-attempt2.txt: all initial nine tests passed.
- features-multiclass-red.txt: an added default-cohort all-three-classes assertion failed (initial generator had zero TIMEOUT).
- features-multiclass-green-attempt.txt: added an explicitly artificial clipped-oscillation/plateau regime; all nine tests passed. No predictive score/model output was consulted.
- features-node-control-red.txt: new matched-node-control assertion failed for absent node_only output. The 6000-bar class-support test passed as part of this run.
- features-green.txt: final ten tests pass, including stronger future-raw-mutation test that changes BREAKOUT to BOUNCE while preserving graph vector and state hash. Tests also cover late history refusal, delayed label maturity, pending horizons, missing future bars, both support/resistance directions, ambiguity, TIMEOUT, finite vectors, non-overlap, deterministic continuity and input preservation.

Command: python -B -m unittest discover -s tests -p test_features.py -v. Results preserved verbatim; test durations are machine/run-specific. No tests from other agents were intentionally run.

## Frozen protocol and exact semantics

Generator version TOY_OSCILLATION_PLATEAU_V2; default generate(seed=20261112,n=1800), accepted n60..10000. Fixed full comparison scenario requests n6000. One continuous TOYUSDT series, minute bars, current bar open exactly prior close; actual toy availability=end. Three 300-bar regimes repeat: smooth oscillation, noisier/larger oscillation, clipped slower oscillation with long low-noise/short-wick plateaus. These are planted artificial scenarios, not a representation of empirically measured regimes. Runtime scenario classification and all random draws are fixed independently of model metrics.

Feature protocol TOY_NEAR_ZONE_V2. Require 48 contiguous prior bars, all available by touch OPEN. Resistance=max prior highs; support=min prior lows. ATR=14 true ranges using final15 prior bars. Zone width=max(.02,.15*ATR), outer barrier displacement=max(.04,.8*ATR). The price floors are arbitrary toy-price increments, not verified instrument tick sizes.

Touch requires current bar range intersect frozen center+-width and prior close approaching from the designated side beyond width. Choose smallest prior-close distance; ties resolve by tuple ordering (support -1 before resistance +1). Current close must lie STRICTLY within the two OUTER barriers. This is deliberately the broader near-zone cohort; current close need not remain within the narrow zone. It differs from the narrower primary proposal in baseline-graph-review.md and cannot be represented as identical. Every selected episode freezes levels and suppresses all new same-instrument decisions with touch.end <= registered label_end, including excluded ambiguous/gapped episodes.

Decision cutoff is actual touch.available_ms. Future observation starts at first FULL bar whose open >= cutoff (ceil to minute); horizon default12 such bars. Labels BREAKOUT/BOUNCE are directional first-passage outcomes relative to frozen support/resistance. If both barriers first touched within one OHLC bar, AMBIGUOUS is counted/excluded. If no hit occurs, TIMEOUT is retained as class3. Missing required future intervals are UNOBSERVABLE, and trailing incomplete horizons PENDING; neither enters examples. Even early first passage has label_available=max availability over ALL horizon bars. label_end is horizon event end, distinct from label_available. No wall-clock now is supplied: callers evaluating at a training cutoff MUST enforce label_available <= training cutoff. Offline input validity/known provenance is checked by the separate adapter, not this builder.

Every eligible example has equal baseline/node_only/graph cohort. Baseline8 features: side, signed center distance/ATR, one/six-bar return, ATR fraction, volume ratio, touch range/ATR, zone width/ATR. Graph nodes are prior24 bars' high/low endpoints (48 nodes), stable order by end/side/price. Each node connects to four nearest other price nodes, ties by index; undirected unique edges, hard slice cap1024, node cap64. Edge statistics are mean degree and mean normalized edge distance. Node-only statistics are nearest candidate distance, confluence fraction within width and node_count/64. Graph13=baseline8+node-stat2+edge-stat2+node-count1. Node-only11=baseline8+node-stat2+node-count1. This allows comparing graph vs same node aggregates, though it is not a complete capacity-matched or economic causal proof.

state_hash covers protocol, symbol, cutoff, prior raw history, touch observation, direction/center/width/barrier, baseline, nodes and edges, excluding outcome/future evidence. Future outcome mutation can change labels without changing state hashes. Output observations contain no zero-imputed unavailable feature: missing mandatory causal history causes refusal/count. Optional market features/L2/POC are not synthesized. Counts are diagnostic event/bar counters, not a partition summing to input length: SUPPRESSED counts bars, label statuses count selected episodes; no-touch bars are not labeled episodes.

## Exact fixed-scenario diagnostic

features-diagnostic.json records n6000:254 eligible episodes, BREAKOUT21, BOUNCE217, TIMEOUT16;21 AMBIGUOUS excluded;3300 suppressed bars;5 already-resolved candidates rejected; no pending/unobservable in this complete artificial history. Raw eligible chronological60/20/20 label support is train14/128/10, middle4/46/1, final3/43/5 (BREAKOUT/BOUNCE/TIMEOUT). Evaluation's purged folds and calendar final holdout may yield different supports and must report their actual counts. Calibration/middle class support is small; do not imply stable calibration or powerful multiclass evidence from these counts. Generator default1800 yields72 eligible (7/60/5) with6 ambiguous; the bound test requires >=60. A ten-test suite is not end-to-end training or simulation evidence.

No scientific edge, graph improvement, real market validity, P0 completion or readiness for owner integration follows from these unit tests. Model/evaluation owners must retain negative results, true holdout boundaries and resource/admission controls.
