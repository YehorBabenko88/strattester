# Explicit financial research sessions

Run the isolated Python 3.12 ML environment with `python -m strattester.research_cli`.
Available commands are `prepare`, `verify`, `diagnose`, `run`, `report`, and
`test-disposable`. Importing this module or using an ordinary strategy CLI does
not register or activate financial research.

`prepare --output NEW_DIRECTORY --openssl-exe ABSOLUTE_EXE --openssl-sha256 PIN
--scratch-root OWNED_DIRECTORY` creates a public RFC test-key engineering package.
The returned config SHA and trust-store SHA are independent command inputs for
subsequent commands; protect them outside the package. Public fixture keys confer
no production producer or owner authority.

`verify`, `diagnose`, `run` and `report` take `--config session.json
--config-sha256 EXPECTED --trust-store-sha256 TRUST_PIN --openssl-exe ABSOLUTE_EXE
--openssl-sha256 EXE_PIN --scratch-root OWNED_DIRECTORY`. Every hash is mandatory.
The v1 config contains version, manifest_path, manifest_sha256, snapshot_path,
checkpoint_path, checkpoint_sha256, trust_store_path, instrument, timeframe_ns,
horizon_ns, available_ns, policy and max_work_bytes. Artifact paths are ordinary
relative filenames confined to the config's directory. Policy is the externally
config-pinned ExportPolicy: producer/epoch/cutoff, exact sources and partitions,
verification time and scope. There is no artifact-selected trust-store hash.

`run --enable-research` defaults to offline signed-export inference. Registration
starts disabled, then this explicit invocation enables only the research entry.
No exchange, store discovery or service management is available. `--output` uses
the bounded immutable result publisher and preserves/rechecks interrupted stages.
`report --enable-research --output NEW_DIRECTORY` computes the same attested
prediction and publishes CSV, static SVG, escaped HTML and provenance. The curve
illustrates the prediction distribution; it is not a performance result.

Connected research requires `run --mode connected --enable-research --profile
PROFILE_JSON --profile-sha256 EXTERNAL_PIN --export-metadata METADATA_JSON
--export-metadata-sha256 EXTERNAL_PIN --connected-output NEW_DIRECTORY`.
The profile encodes HistoryProfile and HistorySource records, including externally
pinned history seals and explicit source locations. Relative SQLite/sharded SQLite
locations must be plain filenames and are resolved from the pinned profile directory;
absolute locations are explicit operator inputs and linked paths are rejected. Metadata contains producer_id,
producer_build_sha, key_id, export_id and issued_at_ns. Only the controlled read-only
sealed versioned history exporter runs. A normal export stops at
AWAITING_PRODUCER_SIGNATURE; no unsigned inference route exists. An explicit
`--sign-public-fixture` permits only synthetic fixture-grid/rfc-key and then uses
the same signature verification, checkpoint and registry inference path. Native
Grid latest-state schemas remain BLOCKED before database access.

`test-disposable` requires every owner plan/signature/trust/hash/identity input.
The CLI always uses its current system clock for owner verification; callers cannot
select a past verification time. Even a verified owner signature is necessary but insufficient: independent native
all-controls evidence is unavailable, so this command returns BLOCKED and never
launches the broker or consumes an authorization nonce. `--launch` does not alter
that rule. Physical G1 remains NOT_AUTHORIZED; trading remains NO-GO.

Structured JSON errors expose exception classes, never raw driver exceptions,
DSNs, passwords or stack traces. Keyboard cancellation returns code 130; runtime
cancellation checks precede stages and result publication. Memory budgets are
software admission controls. Native resource caps are NOT_ENFORCED. Owned scratch
ACLs and pinned OpenSSL installation/library protection remain deployment duties.

## Explicit synthetic prediction-to-backtest experiment

`python -m strattester.research_cli experiment --source experiment.json
--source-sha256 INDEPENDENT_PIN --output NEW_DIRECTORY --enable-research`
runs the existing canonical experiment trainer, reloads the hash-verified
checkpoint, forecasts the exact purged test examples and computes a cost-adjusted
ledger plus Gaussian evaluation from those reloaded-model predictions. The
replayed ledger and metrics must exactly match the canonical experiment before
anything is published. The new output directory contains `checkpoint.json` and
`result.json`; the latter binds every forecast to the model SHA, source SHA,
training dataset SHA, frozen validation-selected threshold, costs and evaluation.
Existing output directories are never reused or overwritten.

The externally pinned source is bounded to 4 MiB and has exactly these keys:
`version` (integer 1), `scope` (exactly `SYNTHETIC_ENGINEERING_ONLY`), `examples`,
`config`, `train_end`, `validation_end`, `test_end`, `holdout_symbols`, `steps`,
`seed`, `fee_bps`, `slippage_bps`, `embargo_ns`. `config` supplies every field of
`StructuralConfig`; omitted or extra fields are rejected. Each example has exactly
`snapshot`, `target`, `timeframe_ns`, `label_end_ns`, `forward_log_return`.
A snapshot has exactly `bars`, `origin_ns`, `coherence_id`, `producers`; each bar
and instrument supplies exactly its financial contract dataclass fields. Arrays
become immutable typed tuples after bounded schema checks. At most 1024 examples,
100000 aggregate bars, 1000 optimizer steps and the configured preparation/work
budgets are admitted. Serialized source plus model work is capped at 512 MiB by
conservative software admission; native resource caps remain NOT_ENFORCED.

Direct JSON labels carry no producer attestation. This command always labels the
result SYNTHETIC_ENGINEERING_ONLY with real_oos BLOCKED and trading NO-GO, even
when a user supplies market-like labels. Forecast availability at the synthetic
origin models experiment ordering and makes no deployment latency claim. There
is no broker, order, service, network or native launch path in this command.
