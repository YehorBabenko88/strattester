# G0 collector independent audit

Audited baseline `33fd4dcf5dd1f7c16130567f0b24915931d8595d`, tree
`e9ebd051277582f68941d79bbe20da917f9c0e45`, on isolated branch
`audit/g0-collector-deep`. Scope is `scripts/physical_g0_inventory.ps1` and
`tests/test_physical_g0_inventory_contract.py`. This is collector software
validation, not new physical evidence or target acceptance.

## Confirmed defects and corrections

- Missing UUID, empty/all-zero/all-FF GUID, or absent hostname could still produce
  a plausible SHA256 identity. Identity is now null with `MISSING` status unless
  hostname and one non-placeholder parsed GUID are present. Arbitrary UUID text
  is rejected. A valid observed hash still requires independent target attestation.
- Identity, OS, CPU, disk, process, service, and sandbox provider failures previously
  terminated serialization and exposed raw provider exception text. Every source
  is now captured separately; failures become `UNAVAILABLE`, without exception
  text. Successfully captured independent sources remain in a blocked report.
- Empty hardware sources and omitted required properties could appear to be
  complete. `MISSING` now distinguishes absent facts from `UNAVAILABLE` provider
  failures. A successfully empty TCP/UDP enumeration remains `OBSERVED`; this
  differs from a failed enumeration returning no usable rows.
- A single CPU, disk, process, or service was serialized as an object while larger
  inventories became arrays. Collection fields now consistently serialize as
  arrays. OS and sandbox remain singular objects or null.
- An absent service `StartType` became an empty string. It is now null and the
  service source is `MISSING`; no default startup type is invented.
- Provider warning/information streams are suppressed. A provider that emits rows
  and then fails cannot publish those rows as complete evidence. The preexisting
  partial-UDP catch already behaved conservatively; its regression test passes.

Readiness remains `BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE` and G1 remains
`NOT_AUTHORIZED` for every outcome. No privilege escalation or fallback probe was
introduced. Source inspection found no DB/network calls, writes, process control,
service mutations, installation, or native execution in the collector. Raw UUID,
command lines, credentials, environment dumps, and provider exception text are not
serialized. Explicit metadata fields such as sandbox path and node name remain
part of the existing local report contract; this is not arbitrary string scrubbing.

## PowerShell compatibility and limits

Actual executables used were Windows PowerShell `5.1.26100.9711` and PowerShell
`7.6.5`. Both parse and execute the same collector using mocked inventory sources.
The tests exercise `SHA256.Create`, `ComputeHash`, `Guid.TryParse`, ordered maps,
array preservation, stream suppression, and `ConvertTo-Json` on both runtimes.
Safe in-process type reflection confirmed `ServiceController.StartType` exists
on both runtimes here; missing-property tests represent missing provider data,
not a claimed PowerShell 5.1 API limitation. PS5 reflection required loading its
standard `System.ServiceProcess` assembly in that short-lived process. No service
was enumerated for this check.

The availability, permissions, and behavior of real CIM/NetTCPIP providers were
not probed. An actual missing cmdlet or provider error becomes `UNAVAILABLE`.
Missing facts and required independent attestations still block acceptance;
software tests cannot prove a VM's identity, namespace confinement, resource
reservation/enforcement, CUDA runtime, database/process ownership, or dependency
isolation.

## Verification and provenance

Every inventory command in the test harness is mocked, with a source command
allowlist checked before invocation. The child process sets a fixture hostname;
it does not alter the host environment. Fixtures, JSON captures, and test logs are
written only by the test harness outside production paths. No actual physical
CIM/process/port/service inventory was run on LS5 or PC4. No native/stopped-stage,
G1, production, installation, or service operations were performed.

- Baseline mocked contracts: **3 passed**.
- First behavioral RED: **16 failed, 5 passed**, confirming missing identity,
  fatal unredacted provider failures, singleton shape, and missing service facts.
- Invalid UUID RED: **2 failed, 6 passed, 31 deselected**.
- Alternate empty-GUID spelling RED: **2 failed, 8 passed, 31 deselected**.
- Final GREEN: **41 passed in 20.93s**, with all new cases parametrized over
  both actual runtimes. Command:
  `..\financial-venv\Scripts\python.exe -m pytest tests/test_physical_g0_inventory_contract.py -q --basetemp=../g0-deep-tmp-release`
- `git diff --check`: passed.
- Initial default pytest temporary-directory access failed before any test body
  (`PermissionError` under `Temp/pytest-of-LS-5`). This was an environment setup
  error, not vulnerability RED. Using a unique workspace `--basetemp` resolved it.
- Full suite is intentionally delegated to the root integration task, which owns
  the approved software-only command and native exclusions; this audit ran only
  the mocked collector contract.

Logs are in the sibling `work/` directory of the worktree and remain reviewable:

| Log | SHA256 |
| --- | --- |
| `g0-deep-red.log` | `ae6e5260a73ea802810e32f9749b67fb3554dc502a0f8a9f5c121fb93da34857` |
| `g0-deep-uuid-red.log` | `1ec140096133d7707922d5ed9d7489d89afa233b64882911f66fe27deb3d9700` |
| `g0-deep-emptyguid-red.log` | `7a21f29a6398f81755fcc696dcfb9cb5ebe204be8c14d1d392804878c08ef764` |
| `g0-deep-release.log` | `7a1c40642903eb72739b8e1aeee0916d397dd3cab80e94f1b06ee7b464cddba8` |

Final source commit/tree/blob IDs are supplied with the PR handoff, avoiding a
self-referential commit ID inside this report.
