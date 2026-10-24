# AlphaFold research integration contract

## Verified repository boundaries
- Source of market candles: strattester.marketdata.sqlite_store.Candle / SQLiteMarketStore.
- Existing research split: strattester.research.validation.chronological_split and walk_forward_folds.
- Independent embedding: strattester.research.protein_geometry.
- Bounded, read-only payload creation: strattester.research.protein_geometry_export.
- Visualization consumer: external Plotly/Terminan adapter, **not yet integrated**.
- Real AlphaFold model: **not integrated**. No upstream source files or weights copied.

## Temporal alignment
A point for close index t is produced from returns in [t-window+1, t].
Its timestamp is timestamps[t]. Future rows must not influence historical points.
Pairwise distance maps are retrospective visualization artifacts; using the full
map for a historical prediction would leak future information.

## Export schema
schema, mode, model, symbol, window, timestamps, closes, points, distances.
Distances and points are ordered by timestamps. Payload is limited to 2048
points (quadratic size); 512 by default. Export is opt-in and never overwrites.

## Remaining implementation gates
1. Verify actual DB schema and build a separate strictly read-only SQLite
   snapshot adapter, with symbol/timeframe/complete-bar filtering.
2. Build Plotly visualizer and align the market line with geometric points.
3. Evaluate protein-inspired pair attention in an optional isolated ML package;
   preserve AlphaFold Apache-2.0 notices if upstream code is actually copied.
4. Add shuffled-series controls and purged walk-forward evaluation.
5. Validate resource budgets, reproducibility and exact dataset hashes.
6. No live trading integration or deployment until independent acceptance.
