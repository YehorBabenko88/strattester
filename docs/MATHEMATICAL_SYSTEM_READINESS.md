# MATHEMATICAL_SYSTEM_READINESS — 2026-10-26

**Status: NO-GO / independent-system-math failed on 5b83d20a (four incorrect target/perturbation assertions); corrected assertions pending exact-HEAD CI.**

## Pinned source evidence
- Strattester integration candidate: `4f3a4bbb9a2f6c0cc3e87fbb0af4fed1dfcc3fd7` (verified commit exists); default main: `37ff7e9d12a4d2dccd788fc493c28557dbe8bcea`.
- Grid main: `d537d525296ef34f727996e240ae6c60102c6082`.
- math main: `ccfe97dd88b1ebee9bd19795002a30d0bd1c1ca3`.
- These are GitHub refs observed at audit start, not proof of physical Grid PostgreSQL schema or math executable parity.

## Independent tests
`research/test_independent_system_math_20261026.py` tests Decimal-vs-float64 log returns and telescoping, sample/population volatility, Decimal Gaussian NLL, simplified roundtrip ledger, target horizon, causal prefix invariance, duplicate events and future availability. Additional negative cases reject NaN/Inf/zero prices, duplicate/out-of-order timestamps and test price-scale metamorphic invariance. Fixed random seed. Hosted matrix Windows/Linux Python 3.11/3.13 publishes JUnit.

## Equations
`r_t=ln(P_t)-ln(P_(t-1))`, `R_t=expm1(r_t)`; sample sigma `sqrt(sum((r-mean)^2)/(n-1))`; Gaussian NLL `ln(sigma)+(y-mu)^2/(2 sigma^2)+0.5 ln(2 pi)` for positive standard deviation. Independent roundtrip cash score `position*simple_return - 2|position|(fee+slippage)/10000 - |position|funding/10000` is not a portfolio simulator.

## Findings
- **P0:** End-to-end Grid producer snapshot -> Strattester feature builder -> Evoformer -> prediction -> financial evaluation is NOT VERIFIED against a single immutable dataset and real availability timestamps. No production acceptance.
- **P1:** `financial_structure_dataset.make_samples` uses `range(window, len(prices)-horizon)`: last possible origin is omitted despite sufficient data. This is a coverage/boundary defect, not proven future leakage. Needs a separately reviewed code change and exact-HEAD tests.
- **P1:** `financial_structure_dataset` computes **population** variance for future log volatility, whereas `math_contract_reference.sample_volatility` uses **sample** variance. Both valid, but target contract must state which and avoid accidental comparison.
- **P1:** Gaussian `scale` must mean positive standard deviation, never log-volatility; verify actual model head conversion and calibration. Full calibration not verified.
- **P1:** Grid ns/ms, event/ingest/available, candle open/close and resampling require pinned physical DDL and producer fixtures; README-level information insufficient.
- **P1:** Triangle orientation, attention masking, gradient and precision parity with actual Evoformer kernels NOT_RUN in this audit branch.
- **P2:** Train-only normalization, purging/embargo, cross-timeframe instrument identity, cost/funding accounting and randomized missing/out-of-order negative cases need full integration evidence.
- **P2:** math repository is not treated as an executable financial oracle; no parity claim.

## Tolerance policy
Decimal 70-digit precision vs Python float64: abs 1e-12 for ordinary log returns and Gaussian NLL; abs 1e-14 for small ledger scores. Float32 kernel tolerance is NOT_SET until concrete hardware/kernel evidence. Nonfinite values, absent units and unverified available times block acceptance.

## Acceptance
Do not merge or deploy. Require exact source/tree SHAs, all CI jobs and JUnit artifacts, frozen Grid dataset SHA256, end-to-end causal perturbation tests, verified model loss and output transforms, independent OOS metrics and real producer contract before GO.
