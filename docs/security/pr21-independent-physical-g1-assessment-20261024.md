# Independent PR #21 physical G1 security assessment — 2026-10-24

Target immutable review SHA: `67301726d250973602b964adabdb9eb8d50d0f13`.
Verdict: **PHYSICAL_G1_AUTHORIZATION_RECOMMENDATION = DENY / NO-GO**.
This is an independent *source review* and CI metadata inspection, not physical G0 or a seven-artifact cryptographic attestation. Do not merge or deploy.

## Verified hosted execution (GitHub workflow metadata)
At target SHA, workflow `financial-integration` run 40109884642 concluded FAILURE. Its seven named engineering jobs (core, data, training, security, math, cpu, integration) concluded SUCCESS; the dependent `system-acceptance-NO-GO` job concluded FAILURE. Other workflows: `tests` 40109884692 SUCCESS, `mathematical-contract-reference` 40109884656 SUCCESS, `alphafold-research-cpu` 40109884775 SUCCESS. These are **workflow/job conclusions**, not independently verified test totals or artifact hashes. Source ZIP, attempt, JUnit, JSONL, SHA256 and provenance comparison: NOT_RUN. PR #15–20 original revisions and ordinary Strattester lifecycle: NOT_FULLY_AUDITED.

## P0: acceptance trust boundary (reproducible source-level bypass)
In `strattester/research/financial_acceptance.py`, `aggregate(reports, sha, required_gates, external, job_result)` revalidates a supplied report using `required_nodeids=r.get('nodeids', ())` and minimum=1. It **does not** independently load the pinned required-node manifest. A forged self-consistent PASS report with one arbitrary node can satisfy this layer. `external={}` is also accepted as PASS when all reports are self-consistent, because the function does not require the four external keys. This is not proof that the deployed `scripts/financial_gate.py` can be bypassed end-to-end: that producer sets four BLOCKED values and performs stronger checks. It **is** a concrete unsafe API trust boundary and must not be treated as a general authorization primitive. Enforce immutable required-node manifest and required external-key schema at the aggregation boundary; reject omitted, extra, non-PASS or un-attested external evidence. Tests must assert forged reports and empty external map cannot yield PASS.

## P1: artifact verification and Windows reparse
`strattester/alphafold_artifact_verify.py` rejects path.is_symlink(), checks regular file after open, uses O_NOFOLLOW only where available. On Windows this does not establish atomic reparse-point/ancestor confinement or a stable identity across path checks/open. Add Windows-specific handle-based reparse rejection and trusted-root confinement, adversarial symlink/junction swap tests, file-id checks and hardlink policy. Do not claim exploit confirmed without Windows execution.

## P1: resource, cancellation and offline
`alphafold_security.admit_pair_shape` is only a preflight estimate; peak intermediate activation, fragmentation, triangle O(N^3), simultaneous jobs and CUDA OOM require runtime enforcement. Checkpoint JSON, atomic rename, crash recovery, cancellation, no-network side effects, SQLite WAL snapshot and service/port isolation need adversarial execution on disposable fixtures. No physical node touched.

## G0 read-only Windows evidence to collect before authorization
On each named machine, collect signed/hashed outputs of Windows build, hostname, user token/privileges, service and scheduled-task inventories, process executable path and signer/hash, TCP listeners and owning PIDs, filesystem ACLs and reparse flags for proposed workspace and binaries, Tailscale/SSH connectivity, local firewall rules, Python/dependency versions, free RAM/disk and proposed PostgreSQL read-only DSN identity. Collection commands must be separately reviewed for no writes and secret redaction. Record exact timestamp, operator, node ID and SHA256. G0 collection itself needs owner approval; no G1 from this report.

## G1 fail-closed matrix
Required: exact target SHA and PR lineage, all 7 job receipts with run_id/attempt/job_id, complete JUnit and JSONL node identities, no skipped/deselected required tests, SHA256 of raw artifacts and ZIP, independent evidence validator, signed Grid immutable snapshot, genuine OOS, CUDA evidence or explicit blocked GPU, model/checkpoint attack results, offline egress denial, atomic checkpoint cancellation recovery, ordinary Strattester lifecycle, and owner-signed command/process/DB/port/ACL isolation plan. Missing, stale, contradictory or synthetic-only evidence = BLOCKED. No transition from BLOCKED to PASS without new verified evidence and explicit owner authorization.
