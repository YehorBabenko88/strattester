# L2 lifecycle transfer plan (source-only, NO_GO)

Source Meta82 b1a4d6a41054f0040a88dc80b585380fb6b4f323. Base canonical data 89cfae0595820137dd33067149dde7f2138a0013 (runtime82). No source deletion, native execution, networking or database operation is authorized by this plan.

| Old symbol | New canonical symbol | Ownership / preservation |
|---|---|---|
| meta_analyse.orderbook.OrderBook.apply/reset | market_data.orderbook.OrderBook.apply/reset | Snapshot/delta IDs, reset-on-invalid, fresh-snapshot requirement, bounded exact Decimal level membership |
| OrderBook._healthy and numerical validation | canonical Math book_summary_metrics / wall_notional | No independent spread/notional/numeric model |
| meta_analyse.orderbook_stream.BookSnapshot | market_data.orderbook_stream.BookSnapshot | Immutable copied Decimal levels, epoch/source observation and structural-validity only; no authenticated source claim |
| meta_analyse.orderbook_stream.OrderBookStream.run | market_data.orderbook_stream.OrderBookStream.run | Reconnect epoch, per-symbol silence, stop-interruptible backoff, monotonic IDs and fresh snapshots retained |
| Raw frame persistence | existing market_data.raw_capture.RawCaptureRecorder + CaptureStore | Inject one canonical durable sink; no second Store/WAL class; persist before publication, unknown storage outcomes stop terminally |
| Meta book_summary UI calculations | Terminan analytics + canonical Math | Not moved into data acquisition package |

Operational policy: canonical public endpoint only, bounded frame/queue/epoch budgets, callback required for durable capture; missing durable sink cannot start transport. Subscription acknowledgement and complete-batch validation precede publication. Immutable snapshots label source authenticity UNVERIFIED and never grant execution authority. Multi-symbol topic routing must preserve symbol identity; malformed/other-topic traffic cannot hide a silent book. Original source remains retained until new sequence/recovery/parity cases qualify.

First regressions: delta-before-snapshot; nonfinite/malformed/duplicate levels; nonmonotonic u/seq; bad update clears validity; invalid symbol; bounded level/frame counts; storage failure prevents callback; reconnect requires fresh snapshot; silent symbol cannot be kept live by other traffic; cancellation propagates; immutable published snapshots survive later deltas. All tests use injected fake sockets/stores and no public/loopback network or native subprocess.

Implemented qualification:113 explicitly selected pure fixture cases PASS on Python3.12 (68 canonical baseline +45 L2/decoder cases). The source state/recovery transfers cover17 OrderBook cases and18 original stream lifecycle cases;10 additional capture-boundary cases cover durable-before-callback SHA links, pre-ACK refusal, duplicate JSON fields, bounded configuration, storage/consumer unknown outcomes, handshake recovery, multi-instrument identity, cancellation and Decimal-string presentation. Tiny1e-1000 quantities remain exact strings. Caller-created snapshots default CALLER_SUPPLIED_UNATTESTED; only this transport publication path declares PUBLIC_PROVIDER_OBSERVED_UNAUTHENTICATED, which grants no trust or execution authority. Math numeric behavior delegates the pinnedfdc SDK.

Limits: no actual public provider, TCP, PostgreSQL, native service, GUI or installed-host acceptance; no continuous acquisition/completeness claim. Source Meta book-summary UI/features, original stores and other unported modules stay retained. The injected capture factory must use the existing canonical durable store; tests use only the reviewed fake Sink. No global auth, duplicate SQL writer, metrics engine or strategy simulation was added.
