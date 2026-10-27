# Independent G0 software inspection and disposable target kit

Baseline source `4b98c95ea0af1ed212c554ba48596312d50d67b5`, tree
`ebd0bd0171d74c5d2fb722ca5f707c91f7f6071e`. Final source/tree and fresh CI
identities are recorded outside the source tree after commit, avoiding a self-hash.
No target has been selected or inventoried. All ten physical groups remain
`NOT_COLLECTED`; `PHYSICAL_G0=PLAN_READY_TARGET_EVIDENCE_BLOCKED`,
`PHYSICAL_G1=NOT_AUTHORIZED`, `TRADING=NO-GO`.

## Final observation contract v2

The authoritative semantics remain [G0 observation v2](G0_OBSERVATION_CONTRACT_V2.md).
`OBSERVED` is a successful nonempty provider observation with required properties;
`EMPTY` is successful zero rows, subject to separate empty-allowed policy;
`MISSING` is incomplete nonempty facts; `UNAVAILABLE` is a failed provider with
partial output discarded; `NOT_COLLECTED` is the manifest-only unobserved sentinel.
None establishes independent identity, trustworthy history, isolation or approval.

New explicit software-only command:

```text
python -m strattester.research_cli inspect-g0-evidence --manifest <ADMITTED_ABSOLUTE_LOCAL_MANIFEST> --manifest-sha256 <INDEPENDENT_SHA256>
```

It checks a single externally pinned local manifest, maximum 128 KiB, using bounded
duplicate-rejecting JSON and existing artifact identity checks. It never resolves
fact paths, receipt references or command captures, executes tools, inventories a
host, connects to a database or uses the network. Output contains states and fixed
reason codes, not raw private facts. A well-formed manifest returns `BLOCKED` and
exit 2, including forged fully OBSERVED facts and hash-shaped receipts. Malformed
input fails closed. This is explicitly **not** a physical attestation verifier.
Portable byte/path checks do not claim native namespace or race confinement.

## Owner-selected Windows VM kit

Use the existing [exact command template](TARGET_G0_COMMAND_MANIFEST.template.json),
[ten-group fact template](TARGET_G0_EVIDENCE_MANIFEST.template.json) and
[private evidence protocol](TARGET_G0_EVIDENCE_PROTOCOL.md) together, not a shell
script generated from arbitrary artifacts. They define G0-01 through G0-05 literal
read-only argv, trusted absolute tool paths/hashes, provider/module admission,
30-second per-command and 8-MiB capture limits, 2-GiB free-disk floor, private ACL
capture, process/port/source ownership and stop conditions. These limits require a
separately verified operator capture boundary; this kit does not enforce them.

Before any physical collection, owner/hypervisor must independently bind the
disposable VM identity, local identity, source/tree/package/tool hashes, sandbox
and private evidence roots, backing volumes/ACLs, owners and exact commands.
No placeholder, protected LS5/PC4, production/shared mount, unknown owner, remote
provider, secret dump, dependency installation, service control or DB connection
is allowed. G0 hashes the native broker without executing it, and does not import
Torch or run GPU/native/research probes. Keep raw stdout/stderr private; publish
only reviewed metadata and SHA256. A provider error can contain secrets.

STOP on missing identity/hash/ownership, unexpected process/network/write,
timeout/output cap, low disk, provider partial failure or sensitive disclosure.
Retain failed captures separately. Cleanup is exact task-owned file review, never
recursive deletion, service/DB cleanup or nonce removal. Owner-v2 G1 plan remains
separately unsigned and unadmitted; it must bind the final source/tree/binary/input
hashes, exact VM, limits, nonce, expiry and independent native evidence. No G1
authorization or full-sandbox qualification is supplied by this cycle.

| Physical group | Current state | Remaining evidence |
|---|---|---|
| Host identity | NOT_COLLECTED | Independent owner/hypervisor binding |
| OS and PowerShell | NOT_COLLECTED | Target versions and provider/tool identity |
| Python base and venv | NOT_COLLECTED | Actual executable roster/byte pins |
| Torch and dependencies | NOT_COLLECTED | Wheel lock, ABI and installed metadata |
| CPU/RAM/disk/limits | NOT_COLLECTED | Actual capacity and separate enforcement |
| GPU/driver/CUDA | NOT_COLLECTED | Real target facts; execution separately blocked |
| Processes/services | NOT_COLLECTED | PID creation identity/executable/owner |
| TCP/UDP | NOT_COLLECTED | Endpoints bound to process identity/owner |
| ACL/namespace/mounts | NOT_COLLECTED | Ancestor ACL/backing volume identity |
| Source/DB ownership | NOT_COLLECTED | Owner roster/producer receipts, no DB access |

## Historical Ubuntu 3.13 timeout

Run `40539165917` attempt 1/job `122312512345` failed at the first mocked pwsh
subprocess, 20 seconds, no stdout/stderr. Python killed it on timeout; returncode
-9 is not proof of OOM. Successful retry job `122316177306` used the same source
but a different runner image (20261025.353.1 -> 20261012.334.1), Python
(3.13.17 -> 3.13.16), region and worker. Adjacent log records around its first
fixture span about 4.381 seconds; this is not an independently timed subprocess.
An intermittent timeout is established. Source defect, resource exhaustion and
startup mechanism remain **unproven**.
Original FAIL and successful retry remain separate evidence, not a RED/GREEN fix.
Forensic report SHA256:
`be9e4954ae11acc81b66eeed20283f41011297c621d2a022c5680704d9898dbf`.

Only the mocked test harness now emits a fixed boundary marker immediately before
collector invocation. Future timeout diagnostics distinguish before/after this
boundary without printing provider data. No retry or deadline increase; the
production collector is unchanged. Before includes runtime/script parsing/mock
initialization; after includes invocation/collector/serialization, not a unique
root cause. This cannot retroactively locate the historical failure.

## Independent source disposition

PR43 HEAD `943095d00d5d56276f3832c42b36b290bea77a84`, tree
`5b9d99f3beb55ba31ea551ef9c1c82488c6f457a`, remains deferred. Four exact-source
adversarial assertion groups reproduced replacement of exposed dataset objects:
execution metrics reflected modified values while retained input_snapshot held
original rows and a receipt still validated. Read/coverage-window, payload alias,
metrics and job/report/token/generation/lease bindings are incompatible with the
integration trust boundary. This is a finding in an **unimported** source, not a
claim of an exploitable integration path. Reproduction log SHA256:
`d55376d3eac2f21a1a047d1a935622f650dc4289422118e59750bae2367eb358`.

PR45/46/47 source HEADs remain respectively
`0b9a9fb2955156710efab07481e307e175ad1ee5`,
`3c7880772bd6f31f9f91e798683ee154eb445664`,
`8dcecddb102622c8d125573ecda69dcdfbdfa263`. No new source import this cycle.
Grid native historical availability/revisions/multi-source epochs require real
producer facts; sealed synthetic contract tests cannot establish them. Signed
funding intake still proves signatures only, not historical truth, and is not
enabled in research runtime. Real OOS, GPU, native enforcement and physical crash
durability remain blocked. No synthetic financial effectiveness is asserted.

## Findings and acceptance

P0: none newly confirmed. P1: missing physical/trust/producer/funding/OOS/GPU/native
evidence and incompatible deferred PR43 data binding. P2: historical timeout
classification unresolved; malformed collector-state schema exception normalized
with an independent-review RED/GREEN regression. Software inspection and marker
tests are software validation only. Full system acceptance must remain BLOCKED.
