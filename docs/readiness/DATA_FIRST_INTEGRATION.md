# PR62 → PR21 Data-First integration

## Identities and import decision

Remote PR21 was rechecked before changes: HEAD57d560a0c75b7061d1735a740da9164384420626, tree6bd152768a924ddd9f0a071b6a4119aa487136cf. Source Draft PR62: HEADbceb60fbee478b03a73fdf68f85291cab3521d8a, tree576f90713955e156e55d3eb9384bbc34b660253b. Current21 is the exact62 base; no textual conflicts exist. Reviewed all22 changed paths, then imported56ae944 andbceb60f with cherry-pick -x, not a branch merge. Per-file source blob/SHA256, reasons and adaptations are recorded in DATA_FIRST_INTEGRATION_PROVENANCE.json. Original1845PASS is historical evidence only. This integration requires1860 mandatory nodes and fresh CI.

## Critical interface review

| Interface | Integration assessment |
|---|---|
| executor.py | Accept coherent read-only snapshot around readiness and consumption; disabled permit never skips data. Generic event-history rows do not prove funding/trade completeness. |
| runner.py | Disabled admission occurs before sync; launch is mandatory and ceil-aligned. Existing direct research path remains available with strict executor gates. |
| sync_engine.py | Category forwarding and bounded incremental pages; closed bars only; committed page progress; missing event-history contract blocks scheduler admission. |
| sqlite_store.py | Persistent category identity, finite/exact-grid validation, WAL snapshot with query_only, input value fingerprint. Snapshot is not historical first-availability attestation. |
| sharded_store.py | Single authoritative store per required snapshot; cross-authority requirements rejected. Explicit existing-file acknowledgement repaired; later unbound files still rejected. |
| bybit_client.py | Full bounded cursor pagination, response streaming/close/retry checks. Integration rejects absent category and malformed falsy cursor rather than silently terminating discovery. |
| StrategyDefinition / DataRequirement | Existing registration preserved; minima/lookback added to fingerprint. Old identities do not certify new readiness. Financial special context remains mandatory. |
| financial-gate-manifest.json | Source exact node additions and documented malformed-timestamp rename retained;15 integration cases added to integration gate125, total1860. No old test counts reused as new PASS. |

## Runtime and financial boundary

The explicit data_first_cli calls DataFirstScheduler, which discovers dynamic linear/inverse/spot metadata, publishes only complete validated universe pages, plans every enabled definition in its injected registry, incrementally repairs missing closed history, validates readiness in a read transaction and executes strategy/backtest before atomic fenced result publication. States: DISCOVERED, SYNCING, PARTIAL, READY, RUNNING, COMPLETED, FAILED, BLOCKED. Qualified category identity is separate from symbol identity. Historical activity intervals are explicit caller claims; absent discovery is MISSING, never invented delisting history.

The current connected CLI deliberately registers only LegacyGridStrategy. A caller-supplied registry may contain other reviewed definitions. Financial research is registered explicitly and disabled by default; its signed-snapshot requirements cannot be inferred from mutable candles. Enabling the financial definition in the candle scheduler produces BLOCKED/NO_DECLARED_REQUIREMENTS. Direct generic execution still rejects the wrong FinancialResearchContext, even after explicit enable. The existing signed offline financial runner remains the sole admitted prediction path. No automatic bridge or producer attestation is invented here. Hosted synthetic financial E2E verifies the real model path separately; local integration tests exercise its admission boundary without Torch/model execution.

## Confirmed RED → GREEN and regression evidence

New integration tests reproduced8 source failures: five malformed terminal cursor values, missing universe category, acknowledged existing shards unusable after reopen, conflicting shard identity accepted at root. Minimal fixes preserve explicit identity and persist acknowledged existing-file identities before publishing the root. A multi-file acknowledgement is not an atomic historical cross-store snapshot; earlier per-file identities can survive an interrupted/failed acknowledgement and retry is idempotent. Scheduler never invokes owner acknowledgement or migrates existing stores automatically.

The original test-writing runs also exposed fixture errors (partition sequencing, SQLite connection thread ownership and legacy .run versus .run_context); these are recorded separately and are not reported as production defects. After correcting fixtures,8fail/5pass was retained before production fixes. Existing synthetic HTTP fixtures were amended with explicit category rather than relaxing validation. Full initial post-fix regression had1failure/224pass because an old universe fixture omitted category; its correction and the original failure are retained.

Final local source suite226PASS;15 new integration cases include actual legacy backtest, partially loaded instruments, archived delisting gaps, read-only snapshot under concurrent delete, cancellation before publication and no duplicate result after restart. Prior PR62 tests retain pagination/categories/new listing, cancellation checkpoints, fresh-instance replay fences, lease expiry and independent ready publication. No local physical smoke, Torch import/forward, training or real connected/OOS execution was performed. Fresh exact-head hosted results must be supplied separately; acceptance remains fail-closed.

## Future read-only Bybit connection proposal — NOT AUTHORIZED

This is a reviewable operational proposal only. LS5_CONNECTED_SYNC=NOT_AUTHORIZED. Do not run the following connected command until separate owner approval names the exact source/dependencies, new root, categories, interval, ticks and budget. Do not use the physical CPU smoke root.

- Network: HTTPS TCP443 to api.bybit.com; DNS resolver access is required to resolve it and is not an isolation guarantee. Automatic redirects are prohibited and unexpected HTTP3xx is closed/rejected; no additional endpoint is admitted. No proxy/netrc credentials; no API keys; no private/order endpoints.
- Public GET endpoints: /v5/market/instruments-info, /v5/market/kline, /v5/market/mark-price-kline, /v5/market/index-price-kline, /v5/market/premium-index-price-kline, /v5/market/open-interest, /v5/market/account-ratio. The current CLI LegacyGrid registry uses only instruments-info and kline. Funding/trades/microstructure remain BLOCKED without independently reviewed history contracts.
- Current CLI defaults: category linear, one tick, concurrency2, shared rate2requests/sec,16 jobs/tick, one successful sync page/job/tick, one HTTP attempt,10second socket I/O timeout,8MiB streamed response,100 discovery pages/category,20000 instruments/category,100000 observations/requirement. Tick30seconds is cooperative; a stuck/uncooperative call is not forcibly isolated.
- Conservative request upper bound for this fixed one-candle-requirement CLI registry:100×categories+16×ticks. Default one-linear/one-tick bound116 HTTP attempts, up to928MiB cumulative response bytes; spot discovery is additionally single-page. This is a bound derived from page/job caps, not a separate global counter. A custom registry/retry policy requires a new budget: failed requests do not consume committed-page progress, and page budget is not a universal HTTP-attempt budget.
- History directory: OWNER_SELECTED_NEW_DEDICATED_ROOT_REQUIRED, not created or authorized. Proposed layout: root/data-first-owned.json; root/state/data-first.sqlite3; root/market/category/shards/manifest.sqlite3; root/market/category/shards/bucket/symbol.sqlite3; SQLite -wal/-shm sidecars. JSON results/events/checkpoints are in the coordinator DB; stdout is captured by the separately approved caller. Root/results and root/logs are configuration paths, not production locations.
- Writes: create owned workspace marker and disposable SQLite schemas; insert/update observed universe metadata, archive claims, jobs/events/leases/progress/results, shard manifest/category identities and accepted historical market rows; SQLite WAL/FULL transactions and ordinary WAL autocheckpoints. No writes to Grid/PostgreSQL or existing unowned roots; no physical/global Python/PATH/firewall/service changes.
- STOP: unexpected host/path/source/schema/category/cursor; unknown launch/calendar/availability/revision or required dataset; source replacement or conflicting values; cancellation, resource admission denial, timeout/rate/page limits or unexpected operation. Preserve retained state/evidence; no production or physical cleanup.

Safe source-only planning command: `python -m strattester.data_first_cli plan-connection`. It creates no client, files or network. A future approved command would be `python -m strattester.data_first_cli run --root <OWNER_SELECTED_NEW_ROOT> --category linear --start-ms <INCLUSIVE_OPEN> --end-ms <EXCLUSIVE_CLOSE> --ticks 1 --allow-network`; the flag is not owner authorization.

## Readiness before exact-head CI

Data-First software/source regressions: verified in synthetic scope; combined exact-head CI required. Real Bybit connection, historical universe/first availability/revisions, required funding/trade/microstructure contracts, Grid coherence, real OOS, GPU, native isolation and physical acceptance remain BLOCKED. Physical G1 is NOT_AUTHORIZED; TRADING=NO-GO. Main and production/physical systems are unchanged. No automatic retry of an uncertain RUNNING strategy is claimed: only committed sync pages resume; uncertain execution remains BLOCKED without a valid independent recovery contract.

Additional confirmed P1: default HTTP redirect behavior could expand approved endpoint scope. An independent synthetic302 regression failed before the fix; requests now set allow_redirects=False and reject3xx before JSON parsing. No real request was made. The dedicated redirect RED and226PASS release evidence are retained.
