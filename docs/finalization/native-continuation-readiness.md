# Native continuation: scope and remaining admission blockers

This cycle starts at owner checkpoint `4f3a4bbb9a2f6c0cc3e87fbb0af4fed1dfcc3fd7`.
The exact candidate and observed CI evidence are published separately after the final commit;
earlier successful runs do not qualify a later commit.

## Implemented, explicitly bounded paths

* Native owner-intent v2 verification uses an embedded, hash-pinned independent Ed25519 implementation. It binds source/tree, the measured executable, the retained deployment package and other input handles, measured local VM identity, resource limits, nonce and expiry. Public fixture owner keys are rejected. Monotonic elapsed time prevents a wall-clock rollback extending admission. Local VM identity is not TPM or cloud attestation.
* The native nonce component creates a durable one-use receipt relative to a retained directory handle. Hosted tests exercise contention, interrupted publication and namespace changes. Receipts and cleanup manifests remain evidence; cleanup does not recursively erase replay history.
* Signed synthetic walk-forward sessions reach feature preparation, fresh models per fold, prediction, verified checkpoint reload, cost ledger and report. Funding remains excluded without signed funding events. These results validate software, not profitability or real OOS.
* Native Grid catalog inspection reports actual capabilities and fails closed when first availability, revisions or producer-issued coherence facts are absent. PostgreSQL lineage inspection uses locked relation identity and a plain-table-only read. It does not export invented history.

## Owner-signable disposable G1 plan

The packaged plan template is `physical-owner-intent/v2`. Populate the exact source/tree,
native executable SHA256, VM measurement, every input SHA256 and resource ceilings.
After constructing the final delivery ZIP, set both `package_sha256` and
`input_hashes.package` to its SHA256 in an external plan, avoiding a circular ZIP hash.
Use a fresh nonce and a maximum ten-minute expiry. No private owner key is supplied.
`--verify-owner` verifies without consuming the nonce or starting a process.

**There is no admitted owner-v2-to-research launch bridge.** The older Python
`test-disposable` command remains a fail-closed refusal, not a v2 launcher.
`--launch` remains blocked before research process creation. Do not interpret a
valid signature or nonce component receipt as authorization or full isolation.

## P1: full native research isolation remains BLOCKED

Experimental PR #36 is deliberately not imported. Its latest hosted run
40364478121 fails before resume at `QUERY_WIN32K_LOCKDOWN`. Earlier failures
40358739845, 40359624109, 40360187246, 40361224313, 40361716905 and 40362940209
remain failures, including child startup errors. Run 40363728918 was cancelled.
The experiment's stdlib synthetic worker is not the actual Torch research runtime.

Independent full native implementation/review was also stopped by an automatic
content filter reporting possible cybersecurity risk. This is an external work
blocker, not a successful review. No alternative agent was used to bypass it.

Required missing evidence includes filesystem/namespace confinement, all-protocol
DNS/UDP/IPv4/IPv6/loopback and descendant egress denial, pre-resume enforcement,
bounded actual research execution, cancellation/crash/replay and independent
adversarial qualification on one exact binary. Direct TCP WFP and token/job
component tests do not prove these properties.

## Physical operations and STOP/cleanup

G0 remains read-only: identify the intended VM, OS, CPU/RAM/free disk, GPU/driver,
dependency versions, service/port inventory and sandbox ACLs; redact credentials.
No target identity or GPU execution is inferred from hosted software tests.
G1 requires separate exact owner authorization and independent QA. Stop before
resume if any binding, expiry, resource or isolation proof is absent; preserve
logs, nonce receipts, hashes and partial output. Cleanup follows an enumerated
manifest only in the disposable VM; never delete a consumed nonce for reuse.

`PHYSICAL_G1=NOT_AUTHORIZED`; `TRADING=NO-GO`;
`PRODUCTION_DB_MUTATIONS=FORBIDDEN`; `MAIN_MERGE=FORBIDDEN`.
