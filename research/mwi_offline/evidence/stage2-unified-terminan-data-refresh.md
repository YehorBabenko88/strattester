# Unified / Terminan / Data Readiness refresh

2026-11-12; read-only static audit. Read full directive C:/Users/LS-5/.codex/attachments/4ce8358d-a584-47f1-8d84-86ef447fa770/Вставленный текст.txt. No imports, DB operations, provider/network calls, services, repository/source/UI edits or training. Only this report written. Physical/runtime/data readiness remains UNKNOWN. No status is inferred from module presence.

## Exact inspected source scope

| Source | HEAD | tree | branch/status |
|---|---|---|---|
| C:/Projects/UnifiedWorkspace/unified-system | 8aab34342d03900ab28e6f5b78acd7558239630c | d491dfa26d31561892232de7425eb75816b842d4 | mission3/runtime-predeploy-20261031; modified mission matrix MD/JSON only |
| C:/Projects/UnifiedWorkspace/Terminan | 7ed3708df53c8850fd11fc8331440bdfee99aa3e | 96963f7e749e73c8c81e7650bdee4f2a0a05923a | mission3/runtime-dashboard-20261031; clean |
| C:/Users/LS-5/.codex/mission-integration-qualified-20261110 | e869d8365c7e54ed3da3739d9cdf15948f37f022 | 8de558ea63b82a0b710a1dcea3459996057cb216 | detached; clean |

These local Oct31 component branches are not latest source claims. Current network PR inventory is independently refreshed by parent in repository-pr-refresh.json; it does not prove a physical deployed version. Prior packet contains historical seam details. The qualified context is later but likewise a source context, not permission to launch it.

## Existing future engine consumption seams

Paths below qualified-root-relative unless Terminan/local explicitly noted.

| Evidence | Source-only classification and usable boundary |
|---|---|
| unified_system/intelligence_gateway.py:23-38 | EXISTING logical observation/research/visualization catalog; catalog docstring explicitly proposed tools, not registered MCP/routes, runtime BLOCKED. publish_research_artifact and get_experiment names do not establish publication or registry. |
| unified_system/intelligence_gateway.py:124-155 | EXISTING bounded query/research preparation; request validation supplies neither rows nor registry claim/page token. Future engine can prepare compatible request metadata only after owner agreement. |
| unified_system/gateway_target_adapter.py:1-5,66-75,96-111 | EXISTING disposable synthetic target/capability registry. Direct local budget/request carries dataset revision, experiment ID, model/strategy parameter digest, principal, assignment/fencing fields; public_submit denied. Explicitly no scheduler/authenticated submit/publication and local journal is not an experiment registry. MWI target registration is EXTEND/BLOCKED owner contract, not automatically present. |
| unified_system/gateway_research_identity.py:96-107 | EXISTING target identity/binding join checks schema hashes, request/job IDs, idempotency, generation, actor, quota owner, producer source hash. Docstring says not resource/job qualification. Preserve exact resource budget and fenced assignment semantics; do not mint new authority. |
| unified_system/gateway_runtime_composition.py:167-177,287-296 | EXISTING DISPOSABLE_ONLY capabilities and identity-bound manifest route; native production engine submit not demonstrated. Future engine receipt needs admitted source/identity/schema before composition. |
| unified_system/storage/manifest.py:27-48,78-106 | EXISTING strict lineage/revision/predecessor-hash candidate codec; publication_confirmed/closure_verified false, publication authority adapter unavailable. Candidate manifest parsing cannot register a model. |
| unified_system/storage/result_publication.py:69-92,118-169 | EXISTING local byte closure stage/copy/readback; native commit_result/reconcile_result explicitly unavailable. Required model/strategy/results artifacts must retain source/dataset/feature/model/split/cost provenance, but native committed publication remains BLOCKED. No second registry/store should be built to bypass this. |
| scheduler_components/placement.py:1-4,10-44 | EXISTING typed Resources/Candidate/Policy/Decision and pure place function. Explicitly working-space calculation, no lease or reservation issued. Decision is not permission to execute. |
| scheduler_components/durable.py:1-3,32-50 | EXISTING provisional preparation journal/resource vector. SQLite serializes local holds, not cluster capacity/leases. Do not convert local checkpoint into distributed scheduling proof. |
| scheduler_components/authority_boundary.py:7-12 | EXISTING closed owner boundary; operations include PublishSegment/AdoptCommittedSegment/ReleaseReservation. Reuse owning admission rather than create parallel authority. |
| local Unified unified_system/fleet_control.py:90-157 | EXISTING approve/heartbeat/elect/submit/place/lease-validation seam with epoch/term/expiry; execution_authorized false. Not audited here as active native scheduler. |
| unified_system/control_api_readonly.py:17-23,50-67 | EXISTING deny-only routes; dataset snapshot/events and session actions AUTHENTICATION_UNAVAILABLE; runtime advertises no auth/authority reads/mutations/snapshots/events. UI route names cannot be shown as usable engine controls. |
| unified_system/operator_control_plane.py:3,29-40 | EXISTING principal/submit/get-command protocols and default authentication unavailable. Manual/scheduled/recovery requests must use owner-approved boundary; no bypass via direct engine callback. |
| Terminan terminan/lab_view.py:27-29,93-102,149-189 | EXISTING strict LAB_SIMULATION reported/unattested market-paper snapshot consumers, quality/provenance validation; not a complete Learning Lab or accepted trained-model registry consumer. Future engine display schema requires versioned additive owner agreement. |
| Terminan terminan/history_overlay.py:64-119,161-180 | EXISTING synthetic unattested scientific handoff, model/source hashes and OOS publication/availability gating; all training/execution/trading false. Suitable causal display semantics, not native admission. |
| Terminan terminan/server.py:54-67,128-138 | EXISTING overlay validation/runtime/infrastructure/research routes. No inspected Learning Lab experiment-create/pause/resume controls. Learning Lab engine API/UI integration is EXTEND/BLOCKED pending owner contract. |
| Terminan terminan/infrastructure.py:83-97 | EXISTING local bounded validated lifecycle snapshot read. Missing/invalid input UNAVAILABLE. Maintain no browser-to-DB connection. |

No independent registry/publication service is justified by these source findings. First integrate declarative versioned artifacts through existing owner-approved storage/registry and display contracts. Until then saved offline results are local artifacts and must retain synthetic/unattested labels. Implemented source is not TESTED/INTEGRATED/PHYSICALLY_VERIFIED by this read-only refresh.

## Data Readiness contract and taxonomy

This is a complete requirement inventory for directive section3 expanded to 48 distinct modalities; it is NOT a claim of captured datasets. Representation taxonomy is orthogonal to readiness: RAW=recorded first-party observation; RECONSTRUCTED=deterministic replay/aggregation from complete primary events with sequence/gap proof; DERIVED=versioned causal mathematical feature; APPROX=explicit proxy/model estimate; UNAVAILABLE=no admitted input/representation for the requested use. Every row below has **actual readiness UNKNOWN; physical presence UNKNOWN; training admission BLOCKED pending ROOT-approved immutable export**. Where required input is absent at execution, emit UNAVAILABLE with missingness reason, never zero. Source column describes the required source, not an observed connection.

Every row must carry dataset ID/hash, source revision/identity, schema+feature version, symbol/market/timeframe/units, precision and aggregation parameters, source event interval, received_at, first_available_at (not late download time), decision cutoff, watermark, replay determinism/hash, per-instrument/window coverage/gaps, explicit missingness mask/reason, provenance chain, row/byte count and peak RAM/disk estimates+measured usage. All these factual values are currently UNKNOWN. Event/received/available timestamps must remain distinct; derived availability=max input first_available and actual feature completion/publication. Reconstructed book requires initial snapshot+complete ordered deltas, and restart/gap boundaries; no OHLC proxy may become L2.

Clock/missingness codes used in table:
- **E** primary event/source timestamps, receipt and first model availability; missing raw observation/latency/receipt -> explicit missing.
- **A** aggregation cannot be available before bin close and all admitted input availability; incomplete bins flagged, never completed with synthetic fills.
- **D** derived feature uses causal completed prefix; missing any required input/insufficient lookback -> unavailable mask.
- **B** book snapshot/delta event+sequence, received/available; gaps invalidate until verified resnapshot, no forward-book inference.
- **L** level exists only after its historical creation/confirmation; broken/unbroken status known only through decision cutoff; future outcome separate mature label.
- **M** metadata valid_from plus observed/available/revision history; later contract revision cannot overwrite past state.

| # | Modality | Required primary source / owning evidence | Representation | Clock / missingness |
|---|---|---|---|---|
| 1 | OHLCV native candles | Grid/Strattester source candle receipts | RAW | A; missing interval/partial candle |
| 2 | OHLCV event aggregation | complete executed trades | RECONSTRUCTED | A/E; trade-sequence gaps |
| 3 | Executed trades/ticks | Grid recorded exchange public trade events | RAW | E; duplicates/sequence loss |
| 4 | Best bid | authenticated book/top quote history | RAW | B; stale/unknown quote |
| 5 | Best ask | authenticated book/top quote history | RAW | B; stale/unknown quote |
| 6 | Spread | same-clock bid+ask | DERIVED | D/B; unsynchronized/crossed quote |
| 7 | Mark price | mark-price endpoint/stream receipts | RAW | E/A; endpoint-specific missingness |
| 8 | Index price | index endpoint/stream receipts | RAW | E/A; endpoint-specific missingness |
| 9 | Funding rate | funding announcements/realized settlement receipts | RAW | E; announced vs realized distinct |
| 10 | Open interest | OI endpoint interval receipts | RAW | E/A; frequency/coverage gaps |
| 11 | Realized volatility | causal returns on valid prices | DERIVED | D; insufficient window |
| 12 | Instrument metadata | versioned instrument endpoint receipts | RAW | M; absent historical revisions |
| 13 | Market status | status/listing/delisting receipts | RAW | M; unknown status intervals |
| 14 | Contract changes | dated tick/lot/leverage/contract metadata | RAW | M; unrecorded revision |
| 15 | Executed buy volume | primary aggressor-side trade events | RECONSTRUCTED | A/E; unknown side excluded |
| 16 | Executed sell volume | primary aggressor-side trade events | RECONSTRUCTED | A/E; unknown side excluded |
| 17 | Delta | buy minus sell volume, units fixed | DERIVED | D/A; missing aggressor evidence |
| 18 | CVD | delta prefix with declared anchor/reset | DERIVED | D; gap/reset invalidates continuity |
| 19 | Trade intensity | timestamped deduplicated executed trades | DERIVED | D/A; no zero for missing tape |
| 20 | Tape acceleration | versioned change in trade intensity | DERIVED | D; incomplete adjacent windows |
| 21 | Orderbook snapshots | recorded exchange book snapshot | RAW | B; no historical book from OHLCV |
| 22 | L2 deltas | recorded sequenced exchange depth updates | RAW | B; dropped/out-of-order sequence |
| 23 | Replayed L2 state | initial snapshot+all ordered L2 deltas | RECONSTRUCTED | B; invalid until resnapshot |
| 24 | Book imbalance | simultaneous validated bid/ask depth | DERIVED | D/B; missing side/depth cap |
| 25 | Depth by price | replayed book and declared depth/precision | RECONSTRUCTED | B; censored out-of-depth prices |
| 26 | Liquidity changes | causal differences between valid L2 states | DERIVED | D/B; reset/gaps excluded |
| 27 | Absorption proxy | executed flow+price reaction, optional book | APPROX | D/E; never actual hidden liquidity |
| 28 | Aggressive trade clusters | primary aggressor events+versioned clustering | DERIVED | D/A; unknown side/cluster censoring |
| 29 | Intraday levels | completed prior intraday causal history | DERIVED | L/D; session/timezone/version |
| 30 | Daily levels | completed day or explicitly developing range | DERIVED | L/A; daily close availability |
| 31 | Weekly levels | completed week or developing labelled range | DERIVED | L/A; calendar/coverage |
| 32 | Monthly levels | completed month or developing labelled range | DERIVED | L/A; calendar/coverage |
| 33 | Historical unbroken levels | point-in-time created levels+subsequent prices | DERIVED | L; future breaks cannot relabel prefix |
| 34 | POC from executed profile | complete price-volume bins+tie policy | DERIVED | D/A; bin precision/coverage |
| 35 | HVN | executed profile+versioned peak definition | DERIVED | D/A; node definition/lookback |
| 36 | LVN | executed profile+versioned trough definition | DERIVED | D/A; no missing bins as zero |
| 37 | Volume profile | complete trades assigned price bins | RECONSTRUCTED | A/E; actual traded prices required |
| 38 | Footprint buy/sell by price | complete aggressor-side trades by price/time | RECONSTRUCTED | A/E; partial footprint flagged |
| 39 | Multi-timeframe structure | aligned causal levels/aggregates per timeframe | DERIVED | D/L; missing timeframe mask |
| 40 | Distance to levels | decision-time price+pre-existing valid levels | DERIVED | D/L; units/tick scale |
| 41 | Breakout behavior | fixed ex-ante level/barrier+future observations | DERIVED | L; mature outcome only after horizon |
| 42 | Retest behavior | fixed breakout definition+subsequent observations | DERIVED | L; path/order ambiguity flagged |
| 43 | Volatility regimes | frozen model+causal return feature prefix | DERIVED | D; train cutoff/model version |
| 44 | OHLC-only volume-profile proxy | candle allocation assumption | APPROX | D; cannot claim executed price profile |
| 45 | OHLC-only liquidity zone | declared statistical price/volume heuristic | APPROX | D; not observed resting liquidity |
| 46 | Historical L2 from OHLCV alone | no valid primary event reconstruction | UNAVAILABLE | B; UNSUPPORTED_INPUT_REPRESENTATION |
| 47 | Hidden liquidity/true absorption | not directly observable from public OHLC/tape | UNAVAILABLE | explicit latent-variable limitation |
| 48 | Model-estimated latent liquidity | versioned probabilistic inference+input receipts | APPROX | D; uncertainty+assumptions mandatory |

For 13-timeframe coverage, instantiate each applicable row per instrument/timeframe; a single 1m export is no evidence for all timeframes. Funding/OI/metadata have their native cadence and cannot be made dense by unmarked fill-forward. Counts/ranges/gap rates/precision/schema/bytes/peak RAM are UNKNOWN until admitted export inspection; no production PostgreSQL connection is allowed by this directive.

## CI and ownership dependency

Parent reports Strattester PR81 main workflow executes pytest tests, which does not collect separately contained research/tests. That path limitation must remain explicit: a green existing main workflow is not new-engine test evidence. PR81 exact refreshed metadata is parent-owned repository-pr-refresh.json; this audit made no hosted calls. Separate new workflow requires ROOT/CI owner ACK (ROOT already asked); do not silently modify broad shared workflow. Qualified Unified .github/workflows/tests.yml:1-24 independently uses scripts/ci_unittest.py and CLI demo across OS/Python matrix; that is a different repo/context and proves nothing about PR81 collection.

Next executable integration work is local owner-scoped artifact schemas/adapters and synthetic tests only. Native experiment submit, committed storage publication, resource reservation, model candidate registration and Terminan Learning Lab controls require exact owner contracts/ACK and admitted artifact evidence. No MWI_RESEARCH_ENGINE_COMPLETE claim follows from this source/taxonomy refresh.
