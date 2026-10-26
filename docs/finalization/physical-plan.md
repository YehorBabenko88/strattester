# Read-only G0 and separately authorized disposable G1

This document is a plan, never authorization. PHYSICAL_G1=NOT_AUTHORIZED,
TRADING=NO-GO, PRODUCTION_DB_MUTATIONS=FORBIDDEN, MAIN_MERGE=FORBIDDEN.

## G0 commands and expected observations

On the explicitly identified proposed node, from a task-owned directory:

```powershell
pwsh -NoProfile -File scripts/physical_g0_inventory.ps1
python --version
python -m pip list --format=json
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total --format=csv
Get-FileHash -Algorithm SHA256 native/StratTester.Native.exe
native/StratTester.Native.exe --diagnose
```

Expected: inventory JSON binds node identity hash, OS/build, CPU/RAM/disk,
service/process identities, listening ports and sandbox ACL summary. Missing
GPU command is UNKNOWN, never GPU PASS. Native diagnose must report BLOCKED,
native_enforcement=false, research_process_created=false. Python package
versions must match dependency-lock.json; this version lock is not a complete
hash-locked offline wheelhouse. Do not dump environments, process command
lines, credentials, connection strings or owner private keys. Collect ACL
details privately with `Get-Acl -LiteralPath <task-owned-directory>`; redact
account names before publication. Inventory cannot prove future confinement.

LS-5 inventory is evidence only for LS-5 at its capture time. Every other
physical node remains unidentified/unqualified until separately inventoried.
All existing Grid/PostgreSQL/MetaAnalyse and other processes/services/ports are
protected. Do not connect to existing databases or change services/firewall.

## Proposed G1 limits and flows

| Operation/flow | Allowed only after separate authorization |
|---|---|
| CPU / memory / wall / output | <=10% / 2 GiB / 60 seconds / 64 MiB |
| Children | one admitted process; unapproved descendants denied |
| Offline network | deny IPv4/IPv6/TCP/UDP/DNS/loopback and proxy paths |
| Connected export | separate reviewed source identities, read-only qualified history only |
| Files | read pinned immutable package; write one fresh output directory |
| DB | disposable fixture DB only; no existing DB writes or connections |
| Processes | owned admitted child only; never stop unrelated processes |
| Services / installation / production | forbidden |

The current native broker refuses arbitrary research launch. Its hosted VM
token/job/handle/direct TCP component proofs do not satisfy full filesystem,
DNS proxy, UDP, arbitrary descendants, output confinement or native owner
verification. Do not run component probes on active physical nodes.

## External owner-signable intent

`prepare` produces an unsigned owner-plan-template.json. Complete and sign a
COPY OUTSIDE the immutable ZIP, after recording final package SHA256, exact
source/tree, native binary SHA256, node identity, short validity interval,
one-shot nonce and resource ceilings. An independently provisioned owner
trust store and its external hash are mandatory; the bundled public RFC8032
producer fixture key is never owner authority. No owner secret is generated
or requested by the package. Signature domain is
`STRATTESTER_PHYSICAL_G1_OWNER_V1\0` followed by canonical JSON.

`test-disposable` checks independently pinned intent, but still refuses launch
until all native controls are independently qualified. Verification alone
does not consume the nonce or authorize G1. Actual execution must atomically
claim a nonce and verify fresh isolation receipts before process creation.
An independent QA review and explicit owner G1 approval remain required.

## STOP, recovery and cleanup

STOP on identity/hash/schema/revision/epoch/signature mismatch, missing
isolation, any egress, resource ceiling violation, cancellation, unexpected
child/port/service/DB activity, incomplete artifacts or interrupted publish.
Preserve logs and partial directories; never interpret partial output as PASS.
Kill-on-close applies only to an owned qualified job; existing services are
untouchable. Recovery uses fresh output roots and verifies original pins;
immutable replay accepts exact bytes only, rejects conflicting publication.

Cleanup manifest must list each absolute task-owned file/directory, process
identity, owned disposable DB data directory and dynamic WFP session. Verify
resolved targets are strict descendants of the agreed sandbox and reject
reparse links before any recursive removal. Remove only those objects after
preserving evidence. Never recursively delete a computed unverified path,
change global firewall rules or stop an installed PostgreSQL service.

## Gate interpretation

Software validation on synthetic fixtures is not financial performance.
Actual native Grid historical availability/revisions/producer epoch, real OOS,
full native isolation, GPU qualification and target-specific G0 remain BLOCKED
where evidence is absent. A green workflow cannot clear external blockers.
