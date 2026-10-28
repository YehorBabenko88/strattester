# Target-bound read-only G0 evidence protocol

This prepares an owner-selected disposable VM. No target is identified or
inventoried by this change. LS5 and PC4 are protected active nodes with no
permitted operations. `PHYSICAL_G0=PLAN_READY_TARGET_EVIDENCE_BLOCKED`;
`PHYSICAL_G1=NOT_AUTHORIZED`; `TRADING=NO-GO`.

The adjacent command manifest is deliberately incomplete and non-executable.
Final delivery supplies exact source/tree/collector/package hashes outside the
source tree, in an external command-admission receipt. Complete the target-bound
command manifest outside the final ZIP so its package pin creates no hash cycle.
VM identity, tool paths/hashes, owners and namespaces require actual
independent provisioning evidence. No current-host identity is substituted.
Do not sign or execute an unresolved template. A command-manifest hash belongs
in a separate admission receipt: it cannot recursively hash itself.

## Target and command admission

1. Owner selects a disposable VM, records independent hypervisor/provider
   identity and signs its association with local firmware UUID/hostname hash.
   Neither a local SHA256 nor a hosted CI runner identity establishes this fact.
2. Inventory owner records exact local sandbox/evidence roots, backing volumes,
   ancestors and owner SIDs. Reject reparses, mapped/UNC/device/ADS paths,
   production/shared mounts and unknown ownership. Portable path preflights
   alone do not prove hostile namespace confinement.
3. Admit exact source/tree/collector bytes and independently provisioned tool
   bytes: both PowerShell versions where supported, Python launcher/base,
   OpenSSL and native broker. G0 hashes broker bytes without executing it.
   Publisher/library/loaded-image verification remains separate. Pin trusted
   local module/provider paths; do not inherit remote module search locations,
   arbitrary profiles, credentials or artifact-selected commands.
4. Complete the structured argv manifest. Substitute only independently admitted
   local literal paths; review the resulting exact argv, working directory,
   environment allowlist, timeout/output cap and capture destination. There is
   no automatic interpreter for artifact-provided shell code in this project.
5. Operator separately admits G0 collection on that disposable VM. This work
   order authorizes preparation, not physical collection or G1 on active nodes.
   Retain private raw stdout/stderr with access restricted to evidence owners;
   publish only reviewed metadata and hashes. Provider errors may themselves
   contain secrets and must not be forwarded unredacted.

Collector commands emit JSON only. Operator capture writes bounded task-owned
evidence files outside source databases; no collector DB connection, write,
checkpoint, service operation or installation is allowed. A zero command exit
means collection completed, never target acceptance. Every required source must
have valid facts and an independently reviewed receipt. `MISSING` and
`UNAVAILABLE` remain blockers; empty TCP/UDP lists are observations, not proof of
network isolation. OS provider implementations/permissions are not mocked into
physical PASS. No fallback to remote queries, elevation or installation.

## Dependencies, process/port/database ownership

Capture exact OS/build/architecture, PS version, CPU topology, RAM/free disk,
GPU adapter/driver facts from the admitted collector. GPU driver names or
AdapterRAM are not CUDA/PyTorch execution evidence. G0-03 uses Python `-I -S`
to avoid site/.pth initialization; compare installed dist-info METADATA and
wheel ABI/hashes offline under independently admitted local paths. Do not import
arbitrary packages, Torch, CUDA probes or native broker under this manifest.
Unknown package files, DLL resolution, code signatures and executable bindings
remain BLOCKED until separately reviewed evidence exists. No dependencies are
installed during G0.

Owner completes this private ledger from observed PIDs/services/ports and
separately attested source administration records, without DB connections:

| Field | Required fact |
|---|---|
| process | PID, creation identity, executable byte pin, service association and owner SID |
| ports | TCP listener/UDP endpoint, interface scope, PID-to-process identity and source owner |
| databases | Grid/PostgreSQL/MetaAnalyse/other source label, exact local path or approved endpoint identity, source owner and `DO_NOT_TOUCH` |
| ownership | Independent owner receipt pin; never infer DB ownership from a process name or port5432 |
| resources | VM reservation, available RAM/disk, package/environment footprint, separate CPU/RAM/wall/output controls |
| cleanup | Exact owned output objects and owner; preserve raw evidence/partial captures and durable nonce history |

Process creation times/executable ownership and database path administration
facts are not furnished by the collector's minimal process list. Missing ledger
entries block admission. Do not dump process command lines, environment, DSNs,
passwords or token material to discover those facts. No running source service
may be stopped, reconfigured or used as a fixture. No production database may
be opened by this protocol.

## Resource, network, STOP and cleanup matrix

G0 capture bounds are requested operator controls:30seconds and8MiB per command,
minimum2GiB free disk, explicit quotas/footprint. Failure or absence of enforced
capture controls blocks collection; source code does not certify them.
Future inference-only G1 ceilings remain CPU10%,RAM2GiB,wall60seconds,
output64MiB,max_processes1. They are neither G0 measurements nor proven native
limits. A workload needing more resources requires a new explicit plan.

| Flow | G0 permission | G1 prerequisite |
|---|---|---|
| local CIM/NetTCPIP/ACL metadata | Only admitted local read-only provider commands | Not a worker capability |
| Grid/PostgreSQL/MetaAnalyse | No connection, mutation or service control | No production mounts/credentials; approved immutable inputs only |
| DNS/TCP/UDP/IPv4/IPv6/loopback/proxy | No G0 outbound command or discovery | Independently proven deny-all including descendants |
| executables | Hash/read metadata only, except admitted PS/Python version commands | Exact loaded executable/dependencies, owner-v2, token/job/namespace/egress/resource proof before resume |
| files | Explicit pinned inputs, private bounded capture destinations | Immutable inputs and bounded owned outputs; no arbitrary namespace access |

STOP on any unresolved pin/placeholder/identity, missing source fact, unknown
owner, unexpected IO/network/child command, raw-secret exposure, timeout,
capacity/quota failure or namespace mismatch. Stop only the operator-owned
capture through its separately admitted boundary; never kill existing services.
Preserve incomplete evidence rather than label completion. No automatic retry
under elevated rights, provider repair or schema migration is permitted.

Cleanup is a separate reviewed list of exact disposable output objects, hashes,
owners and allowed operations. No wildcard recursive deletion, following
reparses, deleting nonce tombstones or altering source artifacts. Physical
power-loss/VM rollback durability remains unqualified. The unsigned owner-v2
G1 template is outside the final package hash cycle; independent QA and exact
separate owner authorization are still mandatory. No native stage is resumed.
