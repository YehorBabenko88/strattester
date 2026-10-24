# AlphaFold-inspired market geometry (experimental, OFFLINE ONLY)

This project explores *structural analogies* between protein contact maps and
market time-series embeddings. It does **not** execute AlphaFold, use biological
weights, treat prices as amino acids, or claim protein models predict Bitcoin.

## Upstream and licensing

Reference: https://github.com/google-deepmind/alphafold
AlphaFold source is distributed under Apache-2.0. The current prototype is
independently implemented, rather than copied from AlphaFold; no upstream
AlphaFold code or model checkpoints are included. Before vendoring or adapting
upstream files, pin the upstream commit, preserve copyright/NOTICE/license
attribution, and mark modifications.

AlphaFold v2's documented full inference is Linux/GPU oriented and uses very
large sequence databases. Do not add those dependencies to Strattester runtime.

## API and safety

`market_backbone(closes, window=16)` produces causal coordinates
(last log-return, rolling return standard deviation, rolling total log-return).
`distance_map` and `contact_map` derive pairwise geometric relationships.
The full contact map is a retrospective visualization; for forecasting at time
t only compute maps from a history prefix ending at t. Do not use a global
future-inclusive map as an input feature.

No live orders, networking, writes to production databases, or modifications to
existing execution paths. This package is not imported by production runtime.

## Scientific evaluation gates

1. Establish baselines: lagged returns, realized volatility, and naive persistence.
2. Chronologically split train/validation/held-out test with purge/embargo.
3. Fit all scaling and thresholds using training folds only.
4. Compare out-of-sample regimes and direction/volatility metrics including fees.
5. Repeat with shuffled returns and random embeddings as negative controls.
6. Declare improvement only with uncertainty intervals and multiple-comparison control.

Until such evidence exists, this is a visualization/research prototype, not a
trading predictor. Running tests: `python -m pytest tests/research/test_protein_geometry.py`.
