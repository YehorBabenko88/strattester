# AlphaFold financial research — independent security acceptance

Status: **NO-GO / NOT VERIFIED** until exact-HEAD CI and adversarial evidence exists.

## Scope and observed risks
PR #15 is an independent financial prototype, not original AlphaFold. Its `financial_evoformer.py` accepts N<=1024 and performs `einsum("bikh,bkjh->bijh")`, with O(B N^3 H) arithmetic and O(B N^2 H) pair storage. A token-count bound alone is insufficient for GPU/CPU memory admission. `protein_geometry_snapshot.py` uses SQLite mode=ro/query_only and BEGIN, but concurrent WAL and path/URI semantics need hostile testing. `protein_geometry_offline.py` calls the shared executor: offline safety requires proof about that executor, not just its wrapper name.

## Mandatory gates (all fail closed)
1. Exact HEAD SHA and complete matrix: Linux/Windows CPU, optional CUDA, dependency audit, static checks. Missing, skipped, cancelled, inconclusive or stale checks => BLOCKED.
2. Pre-allocation admission using batch, N, channels, dtype, layer count and peak activation multiplier. Enforce hard per-job quotas and wall-clock timeout. CUDA OOM => BLOCKED, cleanup and no artifact publication.
3. Weight import: never untrusted pickle or arbitrary object constructors; use a validated tensor-only format, trusted provenance, SHA256 and allowlisted schema, shape, dtype and finite values. Refuse remote auto-download.
4. Artifact output: atomic write/rename, path confinement, no symlink escape, SHA256 manifest, source commit, dataset snapshot, seed, package versions, device and split provenance. Cancel/crash must not mark partial artifacts READY.
5. Database: immutable/read-only URI semantics, reject unexpected schemas, transactionally consistent snapshots, bounded queries, lock/contention timeout, no modification to working DB/WAL, and no future timestamps beyond decision watermark.
6. Leakage: prefix invariance, purged walk-forward with label horizon/embargo, no overlapping train/test labels, training-only preprocessing fits, feature publication time <= prediction origin.
7. Metrics: independently recompute returns, costs, drawdowns, intervals and instrument aggregates. Negative controls, random labels, shifted labels, and fee/slippage stress required. No performance claims without untouched OOS.
8. Side effects: test under blocked sockets, fake broker/order APIs, filesystem write traps and isolated DB; any outbound connection, order submission or production mutation => FAIL.
9. Permissions: workflow read-only GITHUB_TOKEN by default; no pull_request_target executing untrusted code; pin third-party actions by full commit SHA; prohibit secrets and privileged runners on untrusted PRs.
10. Cancellation/concurrency: SIGTERM/KeyboardInterrupt, forced kill, concurrent readers/writer, checkpoint crash and recovery, CPU/GPU cleanup; no deadlocks or orphan tasks.

## Adversarial test plan
- Huge N/B/H, malformed shapes, bool/negative/zero dimensions, NaN/Inf, low memory budget.
- Malicious checkpoint with pickle payload, tampered hash, truncated tensor, zip bomb, path traversal, symlink swap.
- SQLite URI metacharacters, WAL updates, locked schema, deleted/renamed database, duplicate timestamps, incomplete candles, concurrent schema migration.
- Labels that straddle split boundary; shuffled future rows; delayed event ingestion; altered transaction costs.
- Network deny-all, mocked trading API calls that fail tests, cancellation during serialization and training, disk full, GPU OOM.

## Evidence contract
Store exact commit SHA, command, environment, runner OS, device, status, JUnit XML, structured JSONL, SHA256 manifest and reproduction seed. No empty JUnit, skipped-required tests, fabricated GPU PASS or synthetic-only GO.

The `alphafold_security.admit_pair_shape` helper is a conservative **preflight primitive**, not a complete runtime sandbox. Model integration, cancellation, checkpoint loading and hosted CI remain BLOCKED until separately implemented and verified.
