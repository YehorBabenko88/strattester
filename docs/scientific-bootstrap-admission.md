# Historical scientific bootstrap admission

`export_scientific_bootstrap` reports the actual requested symbol/window evidence.
Each dataset records its local row digest, complete-row count, bounds, gaps and
coverage decision. These hashes describe stored bytes; they do not authenticate
an exchange or prove historical availability. Fixed-rate datasets need finite,
closed, exact-grid rows throughout the requested window. At least 41 candles are
needed for the existing nonlinear screen. Missing datasets yield `PARTIAL` or
`INSUFFICIENT`; an empty symbol request yields `BLOCKED`.

Funding and public-trade aggregates currently lack an independent event-history
completeness contract. Even populated or dense tables retain
`EVENT_HISTORY_CONTRACT_UNAVAILABLE` and false completeness capabilities. Full
scientific `READY` therefore remains blocked until those contracts are actually
implemented and validated. L2, liquidations and L2 absorption remain unavailable.

`BootstrapCompletionCoordinator` reads durable DataFirst job dictionaries directly
and also supports inspecting legacy job states. Every job must be successfully
completed, every requested symbol must have a result, and completed instrument
metadata, requirements and input fingerprints must still match. Legacy COMPLETE
states alone carry no scientific admission authority. Cancelled, missing, failed,
active or unknown states cannot finalize a bundle.

`DataFirstScheduler.finalize_bootstrap(root)` opens and closes the actual category
stores and attempts completion independently for each category. `data_first_cli
run` reports these attempts under `historical_bootstrap`; exit 0 requires both
completed research jobs and successful scientific finalization. Otherwise it
returns 2. Research-job completion alone no longer implies full bootstrap success.

Incomplete science can be retained for inspection, but never advances the phase
to `GRID_IMPORT`. `write_handoff` derives `ready_for_grid_import` from the bundle's
readiness and required capabilities. All outputs remain
`HISTORICAL_BOOTSTRAP_ONLY` with `live_promotion_allowed=false`; Grid's independent
import checks remain required. No live promotion or trading authority is granted.
