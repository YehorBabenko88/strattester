# Physical G0 — read-only command and boundary manifest

G0 evidence collected only on LS5. G1 NOT_AUTHORIZED. No application installation, service change, physical DB connection, DB creation, migration, live-market collection or trading was performed. This manifest is prepared for owner signing; no owner signature exists. Hashes prove byte identity only.

## Nodes and compatibility

LS5 identity SHA256 over hostname|SMBIOS UUID: c2950fe16cdd599900386f9c1a1b69ac322d3eefe1a66fe3d48aef7aca01f3a1. Captured2026-10-24T16:38:56Z; hostname LS5, Windows11Pro10.0.26300x64; Ryzen7 5700G8cores16threads; RAM66425480KiB, free36604892KiB at collection. C: size1999291445248, free1736343334912 bytes at earlier16:35 capture. Values are observations, not reservations.

Existing venv Python3.12.10 x64, PyTorch2.14.1+cpu; CUDA build None and cuda.is_available=False. QuadroP4002048MiB, driver582.78 reported by existing nvidia-smi. Hardware/driver does not establish CUDA compatibility; model currently rejects non-CPU tensors. GPU gate BLOCKED. Dependencies frozen in evidence packet, not newly installed. Hosted Linux/Windows3.11/3.13 compatibility is software CI, not PC4 physical evidence.

PC4 and every other proposed node: exact identity/OS/hardware/services/ACL/owner unknown, NOT_CONTACTED/BLOCKED. No SSH/Tailscale/remote probes performed. LS5 is only an observed host, not an approved G1 target.

## Protected assets

All pre-existing processes/services/files/DBs are protected by default, including PostgreSQL18 service postgresql-x64-18 and its ten observed postgres processes. No stop/restart/kill/configuration/role/SQL/WAL/checkpoint action. Grid/MetaAnalyse process ownership cannot be inferred from process names; absence of a matching name is not absence of a workload. Full redacted local service/process/PID/listener inventory is in the local evidence packet, not committed publicly. A process-to-application owner map remains required.

Observed listeners include22,135,139,445,5040,5357,5939,7680,21077,33333,38549,42050,49664–49668,49674,55432,61234,62465,64958; snapshot is time-specific, and none is assigned to this work. No new listener permitted. Actual PID/scope mapping retained in inventory; no assumption that PostgreSQL uses5432.

## Exact current allowed operations and commands

- Read tracked source, git refs/diffs and existing CI metadata/artifacts; write only integration checkout documents/tests/code and work/ evidence, outputs/ deliverables. Push integration branch only; no merge/main change.
- Read local metadata using `./scripts/physical_g0_inventory.ps1` from integration checkout. Script emits JSON on stdout, never writes files or connects to DB/network. Capture under work/ only. Expected schema1,phase G0_READ_ONLY,g1 NOT_AUTHORIZED, no secrets. Any access failure is UNKNOWN, never auto-escalate privileges.
- `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader` uses existing tool, inventory only. Existing venv Python may import sys/platform/torch and report versions/cuda build; no GPU tensor execution.
- Existing venv pytest commands in READINESS.md are software tests over repository fixtures and disposable work/ basetemp only, never a physical G1 experiment or production DB connection. Fixtures may create temporary SQLite under their test basetemp; no working DBs.
- DB operations on all physical DBs: NONE, including read SQL until independently approved exact role/DSN/schema-read plan. DSN/credential names not supplied; no credential value may be collected.

No pip/installer/container/WSL setup, bootstrap/smoke/download/pilot/import CLI, service_worker, service controller, migration, Grid exporter execution or application runtime launch belongs to G0. Their names are inspected as source only.

## Network flow matrix

| Source | Destination | Current rule |
|---|---|---|
| G0 collector | OS metadata APIs | local read only |
| Software offline fixture/model | any remote/loopback socket | deny; targeted e2e connect traps tested, whole-runner sandbox NOT_PROVEN |
| Review control plane | github.com/api.github.com Actions | HTTPS read + authorized integration-branch push; separate from experiment |
| Any research process | Grid/PostgreSQL/MetaAnalyse/Bybit/Telegram | prohibited |
| G0 | PC4/other nodes | no remote operation authorized/executed |

## Resource ceilings and sandbox

G0 proposed ceilings: one collector at a time,512MiB RAM,30s wall, no GPU compute or disk workload. Software verification: one pytest job, OMP/MKL=1,900s wall per gate,2GiB intended process RAM and2GiB scratch disk. Current OS job-object memory/CPU/egress caps NOT_ENFORCED; these are proposed owner-review ceilings, not measured peak guarantees. Aggregate experiment allocations/concurrent jobs still require admission and OS containment. No G1 launch until those controls are independently tested.

Test boundary: checkout under current generated Documents/Codex/work/strattester, scratch ONLY sibling work/tmp-g0-* and evidence files; outputs only final deliverables. Collector records reparse flag and ACL metadata without changing ACL. Existing ACL was not proven exclusive to a dedicated sandbox identity; ancestor junction/reparse and Windows handle confinement remain BLOCKED. Do not run as administrator or reuse a working DB folder.

## STOP, interrupted work and cleanup

STOP on SHA mismatch, dirty/unreviewed code, unrecognized node, producer/epoch/schema/signature mismatch, credential exposure, any service/DB/network side effect, unexpected listener, budget breach, cancellation or missing test evidence. Stop only the job owned by this task; never an existing service/process. Preserve evidence and report rather than retry with elevated permissions.

Cleanup owner: current task operator for software scratch; host/application owner for any later physical plan. Cleanup manifest contains exact generated basetemp/evidence paths only, no wildcards outside work. No automatic deletion is authorized/executed here; preserve RED/GREEN reports and hashes. Abrupt checkpoint publication may leave .checkpoint-*; those require inode/owner/job identity review before deleting, never broad sweep. Known-good checkpoints cannot be overwritten. Existing physical files/DBs/services have no cleanup entry.

## Pending owner signature

Owner must sign exact reviewed commit SHA, command-manifest file SHA256, node identity, run ID, allowed paths/operations/network/budgets, validity period and cleanup owner. Private signing keys must not be given to this task. Current signature status UNSIGNED; G0 materials are PARTIAL, G1 recommendation DENY/NO-GO. A separately signed G1 plan and independent QA are required later; this document grants no G1 permission.
