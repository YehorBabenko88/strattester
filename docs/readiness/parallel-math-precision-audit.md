# Parallel math precision audit, 2026-10-27

Scope: bounded offline CPU feature and structural math only. Baseline f60869686a51693799b4844a1af49c9b39ba45d5; branch parallel/20261027-math. Final source head/tree are in the PR handoff; source blobs, raw logs and log SHA256 values are in parallel-math-precision-evidence.json.

## Confirmed defects and changes

P2 FIXED: the actual feature path computed log(b)-log(a). For adjacent representable binary64 prices at 1e-200 and 1e200 this can erase a nonzero return before float32 export. A 100-digit Decimal oracle constructed from exact binary input values reproduces four failing cases (both price directions at both numeraires). Nearby ratios now use log1p((b-a)/a), with a bounded relative difference; distant ratios retain separate logs to avoid ratio overflow/underflow. Population mean/volatility and eight-element rolling windows retain their definitions. This changes numerical features for existing checkpoints; checkpoint weights/config are unchanged. Reproduce historical features with the pinned source revision; no assertion of cross-revision bitwise prediction identity.

P2 FIXED: predict_snapshot used timeframe before integer validation. Zero raised ZeroDivisionError and negative/bool/float values reached checkpoint access. Timeframe admission now occurs before modulo or model/checkpoint access. Four tests first failed and now pass.

## Mathematical evidence

New tests: 17 total. Six adjacent-price cases (four initially failed), four extreme-ratio/rolling-moment cases, four timeframe cases, two exact prefix-invariance cases, and one checkpoint save/load prediction. The latter observes the actual structural input projection and compares its received features to the Decimal oracle with two recycles; it checks finite distribution and horizon preservation. It does not claim tiny returns necessarily survive learned float32 projections or change output materially.

RED: 8 failed, 6 passed, 0 skipped. Intermediate GREEN: 116 passed, 0 skipped. Final: 119 passed, 0 skipped, 0 failed, 0 deselected. One earlier invocation referenced nonexistent test_financial_pipeline.py; no tests ran. Its error log is preserved in evidence JSON rather than counted as success. Final selected files: test_parallel_math_feature_precision, test_financial_mathematical_verification, test_structural_upstream_differential, test_alphafold_triangle_reference, test_financial_structural_model, test_financial_offline_bridge, test_cycle3_structural_invariants. All under tests/research, pytest -q, fresh --basetemp=work/math-green3-20261027 and --junitxml=work/math-evidence/final.xml. OMP_NUM_THREADS=MKL_NUM_THREADS=1; existing financial-venv only, no installations.

## Prediction-path and pinned upstream audit

Local upstream HEAD c77e5d2a8961d1a353632c462914ff0a32a950f6; modules.py blob 11042362604c72e7005b269c1b5f1ea004f870a1; config.py blob a2355a95be172fa6f79bbb3ed31dda71d7f9cd2d. Existing independent NumPy tests rerun row/column/triangle attention, both triangle multiplication orientations, parameter/input finite-difference gradients, zero masked gradients and recurrence/head for 0/1/2 recycles. Context permutation, unavailable perturbation and active finite gradients rerun. No operator equations were changed in this patch.

The actual model makes one forecast at a validated origin; historical positions exchange information within that origin, rather than supplying per-position causal streaming forecasts. New prefix tests apply to feature extraction, not a claim that attention is causal. Integer nanosecond units, horizon alignment/trained-horizon checks and existing masking contracts remain enforced.

Upstream differences remain explicit: outer-product mean normalizes before projection with count clamp versus upstream projection then (count+1e-3); financial recurrence retains all tracks with gradients versus upstream first-row detached recurrence. No JAX/Haiku execution or pretrained weights are used. P0 newly found: none. P1 acceptance remains OPEN/BLOCKED for GPU/full upstream parity, real OOS/calibration, trusted historical facts and production confinement; these were not assessed as passing. Synthetic fixtures imply no profitability.

G1Execute/Cleanup NOT_AUTHORIZED. Deployment/Trading NO-GO. No physical/native, LS5/PC4, service, DB, credentials, G1 or deployment action. Hosted matrix is automatic; PR handoff reports current CI IDs/status without treating pending as success.
