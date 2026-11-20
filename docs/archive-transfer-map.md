# Archive acquisition transfer map

Source Meta82 b1a4d6a41054f0040a88dc80b585380fb6b4f323. Base Data/L2 9496d0ad33545d71ebc725306318dbed20575cf6. Source remains retained; no original database/files/ref deletion.

| Source | Canonical destination / state |
|---|---|
| archive_resume.ResumeState/strong_etag/resume_headers/validate_partial_response | market_data.archive_resume; exact strong ETag+Range+length, no fallback append |
| archive_partial_state partial_paths/read/save/discard | market_data.archive_partial_state; checksum-bound temporary resume evidence only |
| archive_resumable_download.download_resumable | market_data.archive_resumable_download; bounded injected session, exact content range, atomic final promotion |
| bybit_archive_download.validate_archive_url/download_archive/download_many | market_data.bybit_archive_download; allowlisted public host, streamed byte budget, no redirects, atomic file promotion |
| bybit_archive_plan.archive_url/plan_archive_days | market_data.bybit_archive_plan; bounded closed-day plan, never completeness |
| history_parallel.bounded_map | market_data.history_parallel; bounded tasks, results retain input order; no shared writer |
| archive_file_lock async/sync destination guard | Pending separate path/OS-lock audit; original process tests must stay NOT_RUN under current safety restriction |
| bybit_archive_audit.audit_trade_gzip | Pending Math-owned context-independent epoch conversion; do not copy local numeric formula |
| archive_day_boundary / archive_ingestion | Pending audit+locking closure; local SHA receipts are not provider authenticity/completeness |
| archive_db_import.import_verified_archive / storage_migrations / RawStore / MarketStore | No copied SQL writer/schema. Original preserved blocked until archive batches/checkpoints integrate one canonical CaptureStore/SharedCaptureStore/WAL |
| raw_trades.parse_public_trade / RawTradeStream | Already mostly canonical public_trades+collector. Unique durable-before-dedup/reconnect semantics require parity map; no duplicated stream/parser accepted |
| history.collect_history / BackfillCoordinator | Compare canonical market_backfill before transfer; API pagination never proves historical completeness |
| history.yearly_from_daily / interval numerical coverage | Math/Terminan numerical and analytics ownership; not a Data formula copy |

Validation plan: inspect fixtures before running; injected transport only with audit-denied socket/process construction. Temporary generated files only, never source user stores. Port original pure cases with source location provenance; retain process/actual HTTP/PG cases unexecuted by exact name in report. Test new API absence RED, port reviewed source closure, add bounds/refusal regressions RED→GREEN, build wheel/sdist from committed bytes and test outside checkout. No native/network/live acceptance; NO_GO.

Initial scoped transfer result:213 pure cases PASS (113 baseline/L2 +75 original archive cases +25 strict-boundary cases). Original archive test bodies change canonical imports and provenance header only. Newly reproduced22 failures rejected bool/noninteger/NaN/infinite or excessive transport budgets, noninteger resume offsets/lengths, noncalendar dates and unbounded plan settings before filesystem/transport mutation; regression now green. No old tests deleted or silently skipped. Exact outstanding source fixture names are listed in archive-unqualified-cases.json; these remain unqualified, not moved out of an active passing suite.

Public APIs in this initial transfer are library primitives using injected transport; managed CLI serve remains unchanged. No new canonical SQL writer, Store class, active archive ingestion command or authority is enabled. Filename and sidecar atomicity do not qualify historical completeness, source authenticity or actual multi-process exclusion. Next closure must integrate destination locks, bounded gzip audit via Math, data receipts and canonical writer/checkpoint transaction before archive ingestion can be declared consolidated.
