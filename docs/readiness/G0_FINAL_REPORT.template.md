# G0 v2 final report template — no physical collection performed

Report format: `G0_DIAGNOSTIC_REPORT_TEMPLATE_V1`.
Collector JSON `schema=1`; `observation_contract_version=2`.
Evidence manifest `version=1`. These are separate version namespaces.

## Target and evidence identity

- Owner-selected disposable VM: NOT_SELECTED; label: null.
- Owner/provider identity and independent receipts: NOT_COLLECTED; hashes: null.
- Collection attempted: false. Collection start/end UTC: null.
- Source commit/tree, collector artifact, package and command-manifest hashes: null.
- Operator/reviewer and private evidence location: NOT_COLLECTED; no public identity/path.
- Software test results and CI: fill separately; never copy them into physical fact rows.

The repository currently contains no owner-selected target. After actual owner
selection, a reviewer may update a private copy using independently supplied
evidence. This file neither selects a VM nor grants permission to collect.
Do not substitute LS5/PC4, a CI runner or the developer machine.

## Ten groups of physical facts

| Fact group | Capture state | Observed value / receipt | Admission |
|---|---|---|---|
| `host_identity` | NOT_COLLECTED | null | BLOCKED |
| `os_and_powershell` | NOT_COLLECTED | null | BLOCKED |
| `python_base_and_venv` | NOT_COLLECTED | null | BLOCKED |
| `torch_and_dependencies` | NOT_COLLECTED | null | BLOCKED |
| `cpu_ram_disk_and_limits` | NOT_COLLECTED | null | BLOCKED |
| `gpu_driver_and_cuda` | NOT_COLLECTED | null | BLOCKED |
| `processes_and_services` | NOT_COLLECTED | null | BLOCKED |
| `tcp_and_udp_ports` | NOT_COLLECTED | null | BLOCKED |
| `acl_namespace_and_mounts` | NOT_COLLECTED | null | BLOCKED |
| `source_and_database_ownership` | NOT_COLLECTED | null | BLOCKED |

For each group, retain separately: capture state, source contract/version,
capture UTC, required fields, empty_allowed policy where applicable, reviewed
artifact hash, independent receipt hash, limitations and reviewer disposition.
Unfilled values and receipt hashes stay null. Never replace NOT_COLLECTED with
EMPTY, an empty object, a software fixture or PASS.

OBSERVED means a successful nonempty provider result; it does not establish
physical truth. EMPTY requires successful zero-row collection. MISSING means
nonempty partial/invalid facts. UNAVAILABLE means provider/command failure;
partial rows are not admitted. NOT_COLLECTED means no observation was attempted.
The ten manifest groups differ from the collector's ten provider names; no
automatic provider-to-group completion is implied.

## Readiness and limitations

- PHYSICAL_G0: PLAN_READY_TARGET_EVIDENCE_BLOCKED.
- G1_EXECUTE / G1_CLEANUP: NOT_AUTHORIZED.
- DEPLOYMENT / TRADING: NO-GO.
- GRID_NATIVE_HISTORY: BLOCKED; this reporting work collects no producer history.
- Process privileges, network policy and protected launch: NOT_IMPLEMENTED_HERE.
- Raw evidence remains private; public results contain reviewed hashes/status only.
- P0 confirmed: NOT_ASSESSED. P1/P2 findings: NOT_ASSESSED.

Record actual findings with severity, supporting evidence, exact source HEAD,
reproduction conditions and remaining uncertainty. A syntactically valid report,
zero exit code, matching hash or successful unit test cannot change readiness.
