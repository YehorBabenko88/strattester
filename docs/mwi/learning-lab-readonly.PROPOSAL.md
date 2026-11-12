# MWI Learning Lab read-only proposal v1

PROPOSED_NOT_ADOPTED. This is an inert synthetic artifact profile owned by MWI in Strattester, not an existing Terminan viewer/API contract. Evidence class `SYNTHETIC`, authenticity/publication `LOCAL_UNATTESTED`, adoption `PROPOSED_NOT_ADOPTED` are independent axes. No endpoint, native experiment/job identity, authentication, execution or promotion grant is emitted.

A6 semantic review: FIELD-REVIEW.md SHA256 `7c51f7c2403fa0b46c8bb143d5ba7e45b7385dd58634defdb5e389d2f87698e4`; owner source context HEAD `2a8e2647700dad4f661057235e13f76dc52f091f`, tree `718fed81b980e01b338ab21fdf093da4e3363121`. Exact fixture review and existing viewer compatibility remain pending. No Terminan files change.

## Producer and immutable inputs

`research/mwi_offline/mwi_offline/learning_lab.py::inspect_engine_result` reads an explicitly supplied local regular file, verifies its external raw SHA256, bounds size/depth/nodes/strings, rejects duplicate keys/nonfinite data, and checks closed existing finite-cycle schemas and dataset/model/candidate/holdout joins. It checks aggregate PnL, fees, drawdown and row counts against the reported trades; this is consistency, not simulator reexecution or authenticated provenance.

The fixture under `artifacts/mwi/learning-lab/v1/` projects the preserved Stage2 result from producer HEAD `c7a137bb59fe49edab36218eb012564251e0f317`, raw SHA256 `764517c2910065ca50c51c1c39f526a72ea4e584556051f45883b504ecdc9f17`, 28249 bytes. It does not rerun training or select a different winner. `manifest.json` separately pins the fixture, schema, input and exact projection module bytes. No artifact embeds its own raw file digest. Canonical preview content digests are labelled separately from raw file digests.

`synthetic-result.schema.json` is a closed JSON Schema 2020-12 profile of this one bounded fixture, not a generic future real-data or Terminan schema. Its observed collection cardinalities are intentionally fixed; later profiles need versioned review. It is 67404 bytes, bounded below 128 KiB. Preview is bounded to 64 KiB. Reader input limit is 1 MiB, depth20, total60000 values, 64 object members, 256 rows per array, strings4096 characters, safe integer magnitude <=2^53-1. No graph nodes/edges or executable values are supplied.

## Nine domains

| Key | Current coverage |
|---|---|
| dataset_readiness | Actual local dataset content ID from result; primary data coverage/gaps/revision UNKNOWN, training eligibility false. No snapshot admission. |
| model_versions | Reported model-set hash, exact source context; fitted model artifact not read, algorithm/version UNKNOWN, no active/adopted model. |
| training_progress | UNKNOWN: result lacks job binding and observation clock. No fabricated percent or live queue status. |
| strategy_candidates | Four reported candidates, versions, parent/model joins, thresholds. Local research candidates, no deployment state. |
| oos_results | Producer-declared fresh synthetic holdout, seed20261113, explicit UTC millisecond bounds and frozen strategy; aggregate Brier/log-loss/accuracy/ECE. Per-decision availability/evaluation clocks absent, no empirical market OOS claim. |
| simulated_pnl_and_risk | Actual negative development base/stress PnL, fees/trades/WAIT/refusal counts and reasons. Closed-trade drawdown only, synthetic-zero funding, OHLC fills, no partial-fill/MFE/MAE evidence. No ledger/balance/live realized PnL. |
| forecast_probabilities | UNKNOWN. Aggregate prediction errors are not per-decision probability vectors. Future vectors require three exhaustive exclusive labels BREAKOUT/BOUNCE/TIMEOUT, finite [0,1], sum tolerance1e-8, causal clocks/model/dataset/horizon joins. |
| mwi_graph_visualizations | UNKNOWN. Result has graph-model metrics but no actual bounded graph/typed-port payload. No dangling graph references fabricated. |
| experiment_lineage | Exact producer/result/source/dataset/model-set/selected candidate joins. Owner experiment/job IDs null; no storage publication or registry grant. |

Collections explicitly state bounded selection, count, has_more UNKNOWN and completeness NOT_EVALUATED. Missing domains are UNKNOWN with reasons, not empty-success or zero. WAIT is the actual selected policy. Negative PnL remains unchanged. Metric definitions and cost assumptions accompany the reported values.

## Integration boundary

No conversion to existing closed `lab_view` or `history_overlay` receipt schemas. A6 must review exact HEAD/tree, schema and fixture hashes/lengths before proposing a new viewer adapter. ROOT must separately approve any shared contract/runtime admission. Byte integrity, source ACK and fixture validation cannot authorize physical reads, live data, training, trading or model promotion.
