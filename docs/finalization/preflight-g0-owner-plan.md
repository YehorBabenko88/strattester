# Read-only G0 and owner-signable G1 preparation

Base PR21: `d27ad12ea32e4e8fa2cabed0952a516dbcbc6418`. This is a plan,
not an executed inventory, authorization, or qualification of LS5/PC4. All
physical target identities, publishers and deployed producer facts remain unknown.

## G0 intake on the separately selected disposable VM only

Collect exact VM identity, OS/build/architecture, CPU, RAM/free disk, GPU/driver/
CUDA if present, Python/PyTorch/dependency versions, existing service names and
listening ports, and sandbox path/ACL ownership. Names of credential sources may
be recorded; never dump environment values, DSNs, tokens or private keys.
Existing Grid/PostgreSQL/MetaAnalyse and other active processes are outside scope.

Read-only command examples for the future authorized operator:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-Volume | Select-Object DriveLetter,Size,SizeRemaining
Get-Service | Select-Object Name,Status
Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
Get-NetUDPEndpoint | Select-Object LocalAddress,LocalPort,OwningProcess
Get-Acl -LiteralPath '<operator-selected-disposable-root>'
Get-FileHash -LiteralPath '<pinned-native-broker>' -Algorithm SHA256
Get-AuthenticodeSignature -LiteralPath '<pinned-python-base-executable>'
```

Do not run these against active LS5/PC4 as part of this delivery. Firmware/VM
identity must be independently measured on the intended VM and bound to the
owner plan; a local hash is not TPM/cloud attestation. Missing GPU facts remain
BLOCKED, never CPU-emulated. No applications/services/drivers are installed here.

## Separate executable-byte verification

Create an external pinned manifest (version1, files1..32) listing exact local
absolute paths, logical names, expected SHA256 and size_bytes. Include separately
the native broker, venv Python launcher, actual base Python executable and the
signature verifier; record dependency-library/publisher evidence separately.
Example entry, with all placeholders filled from trusted build/provisioning:

```json
{"version":1,"files":[{"logical_name":"native_broker","absolute_path":"C:\\DISPOSABLE\\StratTester.Native.exe","sha256":"<64 lowercase hex>","size_bytes":0}]}
```

The placeholder size0 is invalid deliberately. Run only after completing and
independently pinning the manifest:

```text
python -m strattester.research_cli verify-executables --manifest <absolute-local-manifest> --manifest-sha256 <external-pin>
```

Expected success is `FILES_VERIFIED_ONLY`, `execution_binding=UNQUALIFIED`,
`dependency_closure=NOT_PROVEN`, `physical_g1=NOT_AUTHORIZED`. This command never
executes listed files. It checks the full roster/budget before target IO and
rejects nonlocal/device/ADS/traversal aliases, reparse/hardlink or digest/size
mismatch. It does not attest publisher, dependent libraries, loaded images,
future pathname identity or a measurement-to-launch race. OS guarantees remain
required; this command cannot substitute for the blocked native bridge.

## Trust and owner policy required before any future G1

* Independently provision role-separated owner and producer roots. Pin exact
  trust-store bytes and key IDs; define validity, rotation, revocation and rollback
  policy. Repinning must replace already loaded immutable policy snapshots.
* Known public fixture producer keys are never real producer/owner authority.
  Hashes alone do not establish trusted issuer provenance.
* Complete the external owner-intent v2 with exact source/tree/native binary,
  final package hash, VM identity, every input hash, fresh nonce and expiry no
  longer than10 minutes. Both package_sha256 and input_hashes.package bind the
  completed ZIP; keep the unsigned/signature files outside that ZIP.
* Add the separately pinned executable inventory and trust-policy evidence as
  input artifacts where appropriate. Their presence is not proof that an
  unimplemented execution bridge enforces their contents.
* Existing maximum requested limits remain CPU10%, RAM2GiB, wall60s, output64MiB,
  max_processes1 and synthetic_cpu_inference only. These are owner-plan ceilings,
  not presently proven OS enforcement for actual research. CPU cooperative
  training slots are a separate software mechanism, not these sandbox controls.

## Network and operation matrix

| Phase | Network | Processes / DB / files |
|---|---|---|
| Development/hosted CI | Explicit GitHub/toolchain package traffic only where needed | Task-owned code/builds/disposable test fixtures; no production writes |
| G0 plan/inventory | No required Grid/exchange egress | Read-only identity/service/port/ACL/file evidence; no service controls |
| Future offline G1 | Deny all DNS/UDP/IPv4/IPv6/loopback/descendant/proxy egress, independently proven | Only exact owner-authorized worker, retained inputs and bounded outputs; no DB or credentials |
| Connected native Grid | Not enabled by this plan | Requires real producer history/availability/revision/cross-store epochs and separate qualified export |

## STOP, recovery and cleanup

STOP before resume if any signature/key-role/expiry/nonce/hash/VM/source/limit or
native control evidence is missing. --launch and test-disposable remain refused.
Do not turn component CI or a signed assertion into physical authorization.
Preserve original logs/JUnit, partial outputs and consumed nonce receipts.
Software checkpoint/result replay is tested; power-loss and VM rollback durability
remain unqualified. Cleanup must enumerate exact task-owned disposable paths,
process identities and receipts; never recursively erase nonce history, touch
active services, production databases or another user's worktree. Owner and
independent QA must approve the exact disposable G1 separately.

`G1=NOT_AUTHORIZED`; `TRADING=NO-GO`; `MAIN_MERGE=FORBIDDEN`;
`PRODUCTION_DB_MUTATIONS=FORBIDDEN`.
