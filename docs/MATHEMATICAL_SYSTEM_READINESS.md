# MATHEMATICAL_SYSTEM_READINESS — independent review

Status: **NO-GO / PARTIALLY VERIFIED**. Baseline: Strattester PR #21 commit `67301726d250973602b964adabdb9eb8d50d0f13`. Audit branch: `parallel/alphafold-grid-math`. This document records only verified observations, not producer parity.

## Source evidence and limits
- Strattester: `research/math_contract_reference.py`, `financial_structure_dataset.py`, `financial_evaluation.py` inspected at the pinned PR #21 SHA. The latter evaluation module is **not present in the audit branch** at the CI checkout; therefore integration assertions about it are NOT_RUN, and mathematical CI previously failed during collection.
- Grid README inspected from the repository default branch: `candles_1m` and `footprint_1m` are executed public trade flow, not resting order-book liquidity. README is **not** a physical PostgreSQL schema or proof of event/availability columns.
- math README inspected from the default branch: offline mathematical laboratory and illustrative Bitcoin roots, not an executable financial Gaussian-NLL/Evoformer oracle. License not granted by default. No parity claimed.
- google-deepmind/alphafold README inspected: biological AlphaFold 2 inference implementation. No financial correctness or architecture equivalence inferred.

## Equations and numerical policy
- Log return: `r_t = ln(P_t) - ln(P_(t-1))`; simple return `R_t = expm1(r_t)` when representable. For tiny returns use `expm1`, never `exp(r)-1` blindly.
- Population volatility `sqrt(sum((r-mean)^2)/n)` and sample volatility `sqrt(sum((r-mean)^2)/(n-1))` are distinct; require explicit named target and units.
- Gaussian NLL: `ln(sigma) + (y-mu)^2/(2 sigma^2) + ln(2*pi)/2` for **positive standard deviation sigma**, not log-sigma. Convert log-sigma explicitly and bound extremes.
- Financial ledger: `position * simple_return - 2*abs(position)*(fee_bps+slippage_bps)/10000 - abs(position)*funding_bps/10000` is a simplified independent round-trip score, not an execution simulator.
- Candle interval: `[open_ns, close_ns)`, closed only when `close_ns <= watermark_ns` and `available_ns <= prediction_cutoff_ns`. Do not silently treat an exchange last-inclusive millisecond timestamp as an exclusive end.
- Pair/triangle: dependency availability must be checked on every path `i->k->j`, not only output pair `i,j`; attention softmax must normalize over valid keys only, with fully masked rows handled explicitly.
- Float64/Decimal tolerance: absolute <= 1e-12 for ordinary log returns and NLL, relative <= 1e-10 for representable simple returns; compare float32 at documented looser tolerances per kernel and dtype. Never silently permit nonfinite results.

## Severity
**P0:** no pinned executable producer-consumer contract across Grid snapshots, PIT availability, resampling and trained model; end-to-end correctness NOT VERIFIED.
**P1:** mismatch risk between population target volatility and sample reference; Gaussian scale semantics; simplified cost ledger; pair/triangle path dependency and train-only normalization require integrated adversarial checks.
**P2:** CPU/GPU gradient finite differences, float32/64 tolerances, instrument/timeframe metamorphic permutations, randomized property suites and source provenance remain incomplete.

## Evidence and acceptance
- Mathematical workflow run 40112097565 on previous SHA `afeab9e8e71d5ebc0114cd0ed693db613a86fbcd`: **FAIL 4/4** (ModuleNotFoundError during collection); general tests workflow 40112097394: SUCCESS. This does not constitute mathematical acceptance.
- Independent Decimal, unit, PIT and timeframe oracles added in audit branch. Current HEAD requires a fresh full matrix. No claim of actual Grid/math parity, live trading readiness or production safety.
- Release requires pinned upstream Grid and math SHAs, exact DDL/adapter fixtures, full pipeline on immutable snapshots, independent baseline reproduction, gradient/attention/triangle checks and non-skipped CI evidence.
