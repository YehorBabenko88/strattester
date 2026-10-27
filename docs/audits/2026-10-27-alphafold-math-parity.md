# AlphaFold and financial math parity audit — 2026-10-27

Scope: refreshed PR21 `f60869686a51693799b4844a1af49c9b39ba45d5`, branch `parallel/alphafold-math-parity`. Source audit and bounded synthetic CPU tests only. No G1, trading, live data, production DB, service operation, GPU, or main merge.

## Pinned sources

* [Original AlphaFold](https://github.com/google-deepmind/alphafold/tree/c77e5d2a8961d1a353632c462914ff0a32a950f6), `alphafold/model/modules.py`, `config.py`. Fresh read-only source clone, no upstream execution or weights.
* [Grid](https://github.com/YehorBabenko88/bybit-cluster-grid/tree/d537d525296ef34f727996e240ae6c60102c6082): `grid/schema.sql`, `grid/db.py`, `grid/migrations.py`, `grid/archive_materializer.py`, `strategies/example_poc_volatility.py`. No database connection. Public trade flow/footprint is executed volume, not resting depth.
* [math](https://github.com/YehorBabenko88/math/tree/ccfe97dd88b1ebee9bd19795002a30d0bd1c1ca3): this main tree contains README.md only. It describes a browser laboratory and illustrative polynomial roots, and grants no default license. There is no executable returns/volatility/horizon reference to compare here. Standard equations are independently derived; no implementation copied.

## Mechanism disposition

| Area | Original AlphaFold | Executed financial adaptation / assessment |
|---|---|---|
| MSA row | LayerNorm, scaled query/key, pair-derived bias, gated values | Same index equations in mapped small NumPy references. Financial tracks are aligned historical instruments; not biological MSA. Query mask additionally zeros output. |
| MSA column | Attention over sequences at each residue | Same grouping equations, instrument exchange at one forecast origin. No per-position causal forecasting claim. |
| Outer product | Project summed products plus output bias, then divide by count+1e-3 (`modules.py:1685`) | Mean products over overlapping tracks, then project and add bias; zero empty edges. These differ even with the same mapped weights; intentional adaptation, **not exact upstream parity**. |
| Triangle multiplication | outgoing `ikc,jkc->ijc`, incoming `kjc,kic->ijc` | Version-two orientation matches pinned config. Distinct projections and asymmetric masks exercise index swaps. |
| Triangle attention | Fixed vertex grouping; query/key third-edge bias; ending swaps vertices | Existing scalar NumPy reference plus complete trunk reference exercise both orientations. Arbitrary edge masks are not provenance/dependency closure enforcement. |
| Pair transition | Residual attention/multiplication and transition | NumPy oracle now recomputes all residual updates from inputs/parameters; no captured layer outputs. |
| Recycling | Previous first MSA row, pair and geometric state; `stop_gradient` in outer loop | All MSA tracks and pair recur with gradients across passes; no geometric state, IPA or structure head. Test this financial behavior; do not call it original recycling parity. |
| Forecast | Biological heads/geometry | Target-track last available token plus pooled pair; Gaussian log-return mean and positive distribution scale. Scale is not a realized volatility label or guaranteed calibration. |

Trunk reference uses mapped parameter arrays, independently implemented NumPy arithmetic, scalar attention and multiplication loops, scalar outer products and normalization. Tests cover float32/64, batch 2, asymmetric padding, an empty context track, depths 1/2 and recycling 0/1/2. Selected input and largest-magnitude parameter coordinates for each operator family are checked against finite differences of that full reference. This is finite-domain evidence, not a full Jacobian, upstream JAX/Haiku execution, pretrained inference or empirical market validation.

## Financial semantics and remaining limits

* All typed boundary timestamps and horizons use integer ns; conversions above 2**53 are checked without a float roundtrip. Candle event interval is half-open; close/ingest/availability/watermark guards admit equality and reject boundary violations.
* `feature_tracks` computes log-price differences, trailing means and **population** volatility over at most eight values, including the initial synthetic zero return. Decimal tests reproduce actual production channels at price scales 1e-200/1/1e200. The proposal `grid_strattester_ml_math_v0.1.md` describes **sample** volatility. These are distinct estimators; no claim of contract-wide volatility parity, and changing estimator would require versioned feature/checkpoint migration.
* Legacy `make_samples` has a **bar-count** horizon, preserves caller timestamp units, and uses population future volatility with a floor before log. Decimal targets and future-perturbation checks pin that path. It is not an ns-aware Grid adapter.
* Structural experiment horizon is integer ns and must equal label_end-origin and align with timeframe before features/model allocation. Caller-pinned synthetic labels are not independently authenticated market outcomes. Real OOS remains blocked.
* Grid candles use PostgreSQL `timestamptz` and `numeric`, not integer ns. Native candle DDL does not supply all immutable availability, revision and cross-producer coherence facts required by Strattester. `range_pct=(high-low)/close` in Grid's example is a range feature, not return standard deviation. No equivalence is asserted.
* All visible positions in the structural model are available at one origin. Endpoint-derived pair masks remove unavailable tokens before projection; this is not an arbitrary per-query event-time/dependency-closure engine. Internal historical tokens may exchange information.
* Extreme finite inputs are not universally guaranteed stable: mapped float32/64 finite-domain tests and nonfinite-result rejection do not certify all representable tensors, lower precision, GPU, or price cancellation near machine precision.

## Findings

| Priority | Finding | Disposition |
|---|---|---|
| P0 | No new confirmed P0 in audited scope | Not proof of absence outside scope. |
| P1 | Full original AlphaFold parity is absent (OPM, recycling gradients/state, geometric modules, initialization/training) | Explicitly blocked; do not promote CPU equation evidence to full parity. |
| P1 | Native Grid availability/history/coherence and authenticated real outcome labels unavailable; math has no executable reference at pinned main | Cross-system and real OOS acceptance remain blocked. |
| P2 | Empty-mask row attention in float16 divides by zero because 1e-9 underflows | Fixed with dtype-representable denominator; RED then GREEN forward/backward regression. Structural model still admits only CPU float32/64. |
| P2 | Proposal sample-volatility differs from actual population feature/legacy target estimator | Pinned by tests and disclosed; no silent checkpoint semantic change. |

## Verification and evidence

New nodes are registered in the existing exact-node financial manifest: math +17, cpu +11. Existing hosted workflow checks out PR head SHA explicitly. The focused set includes 28 prior tests and 28 new tests. RED: 55 passed / 1 failed (float16 empty mask); GREEN: 56 passed. Mutation probes detected incoming orientation (8 failures), disconnected outer product (8 failures), and detached recycling gradient (1 failure / 1 pass). Sources were restored with matching SHA256. See the Draft PR/evidence package for the final full-suite result, source SHA256 manifest and hosted exact-HEAD CI status; this document does not assert a hosted result. Earlier attempts with inaccessible system pytest temp or incomplete dependency installation are environment/setup failures, not used as parity proof.

Acceptance remains NO-GO. No G1 or trading authorization follows from these tests.
