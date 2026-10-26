# Windows native broker: component implementation, research execution blocked

This is compiled Windows x64 managed-native interop source targeting .NET Framework
4.7.2. The executable has **no authorized research process creation path**.
It includes a separately guarded hosted-only LPAC experiment with an owned,
synthetic embedded Python payload. `--launch` always returns JSON BLOCKED and exit 78 before
opening arguments or running commands. No G1 authorization is possible.

Implemented Win32 components, reachable only through the disposable VM component
test mode:

* Duplicate the current process token using `CreateRestrictedToken`, remove all
  remaining privileges using `AdjustTokenPrivileges(SE_PRIVILEGE_REMOVED)`, then
  independently query the token privilege count and require zero. These tokens
  are assigned only to owned component probes; group SIDs and filesystem access
  are not confined.
* Create an unnamed job with kill-on-close, job memory, active-process count 1,
  process CPU time and CPU hard-cap limits. Query the actual kernel values and
  compare them with literal expected values, then close the job. Query success
  demonstrates API configuration, not CPU/RAM limit enforcement.
* Open a local artifact with retained ancestor and leaf handles denying
  write/delete sharing. Open reparse points themselves, query attributes/tags,
  verify final handle paths, reject hardlinks/device/ADS paths, and hash a bounded
  leaf while retaining volume/file identity. Hosted scratch fixtures test normal
  hashing, conflicting writes/ancestor renames, hardlinks and parent symlinks.
  This is an input artifact component; it does not confine arbitrary filesystem
  access or exclude preexisting writable mappings.
* Launch only the executing assembly with literal sleeping probe arguments,
  restricted token, no inherited handles and CREATE_SUSPENDED. Assign and query
  the job before resume, require the benign probe to remain alive, close the job
  and verify termination. Direct process handles provide cleanup on errors.
  These older component modes cannot launch a caller-provided executable, script
  or research workload. The separate LPAC fixture path is described below.

## Hosted LPAC experiment (research execution remains blocked)

`--selftest-sandbox COMPONENT_TESTS_ONLY` requires the same disposable-host
accident guard. It is **not an authorization API** and must never run on LS5,
another physical host, or a production service. The workflow
`windows-lpac-experiment.yml` prepares a SHA256-pinned Python 3.12.10 embedded
archive and an independently implemented Python malicious probe. The code stages
these into a fresh owned runtime and grants its unique package SID read/execute
only. It replaces the complete new AppContainer profile tree's DACL with
read/execute access; the profile does not provide a writable output directory.

The experiment requests LPAC through
`PROC_THREAD_ATTRIBUTE_ALL_APPLICATION_PACKAGES_POLICY` and a
`SECURITY_CAPABILITIES` structure containing no capabilities. It uses a
restricted token retaining only `SeChangeNotifyPrivilege`, the child-process restriction, an atomic job-list
attribute, and a handle list containing only retained read-only stdin and one
combined stdout/stderr pipe. It creates the child suspended and independently
checks its token identity, the exact `SeChangeNotifyPrivilege` LUID and enabled
attributes, zero capabilities, LPAC state and
job limits before resume. Every runtime leaf is held with denied write/delete
sharing during execution. A bounded capture reader kills the job on output
overflow; wall time, cancellation and error paths terminate and reap the child.
Job configuration includes kill-on-close, one active process, CPU time, CPU rate
and total committed job memory. Configuration alone is not enforcement proof.

The one retained privilege bypasses directory traversal checks; it does not grant
file read, directory listing, creation, write or deletion. The zero-privilege
LPAC failed before Python entry; the hosted experiment tests whether restoring
traversal alone permits the private runtime beneath ordinary user ancestors.
No shared ancestor or Windows directory ACL is widened. The older
zero-privilege component remains separate; its count must still be zero.

The headless path also requests and queries Win32k syscall lockdown. A unique,
non-visible window station and `Default` desktop provide the private USER
namespace required for session-0 startup. Their protected DACLs grant only the
current broker user, SYSTEM and this package SID; mandatory labels must be Low
with no-write-up. The broker queries the names, visibility, exact DACL principals
and rights, and integrity-label bytes before admission. It restores its own
original station immediately after creating the private desktop and retains
the private handles through child cleanup. Existing interactive/service window
stations and desktops are never modified.

The owned malicious payload attempts input/canary/profile reads and writes,
IPv4/IPv6 TCP/UDP/loopback, DNS through `DnsQueryEx`, parent-process access,
ordinary named-object and registry namespace access, child creation, memory
exhaustion, CPU exhaustion, endless output and sleep. A loopback UDP53 observer
must first observe a real unrestricted DNS query and return NXDOMAIN. The same
API from LPAC must return access denied and produce no observer traffic. Network
timeouts and unsupported address families do not count as denial. Separate
resource probes must actually trigger the bounded behavior, followed by a
synthetic Python mean/variance result over the inherited input transport.

No successful component receipt means full sandbox or G1 acceptance. The
filesystem system-runtime allowlist, registry/profile writable-state audit,
all network proxy mechanisms, authenticated launch/replay lifecycle and
end-to-end owner-authorized admission remain qualification requirements. The
experiment's result always reports `native_enforcement=false`,
`owner_authorized_research=BLOCKED` and
`full_filesystem_qualification=INCOMPLETE`. Hosted failures retain the failing
phase; do not turn a failed probe into PASS by accepting an unrelated OS error.

API references: [Microsoft LPAC launch example](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer),
[process attributes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
[DNS query request](https://learn.microsoft.com/en-us/windows/win32/api/windns/ns-windns-dns_query_request),
[Microsoft DNS server-list sample](https://github.com/microsoft/Windows-classic-samples/blob/main/Samples/DNSAsyncQuery/cpp/DnsQueryEx.cpp).

`--diagnose` reads only the executable hash and existing current-process job
membership. It does not create tokens/jobs/processes, set policy, touch services,
or test sandbox enforcement. It always reports native_enforcement=false,
component_validation=NOTRUN and research_process_created=false.

## Build and safe tests

From the repository root on Windows with Python 3.11+ and .NET Framework 4.7.2+:

```powershell
python scripts/build_windows_native.py --output C:/task/native-build --cache C:/task/native-cache
$env:NATIVE_BROKER='C:/task/native-build/StratTester.Native.exe'
python -m unittest discover -s tests/native -v
& $env:NATIVE_BROKER --diagnose
```

The script downloads exact official NuGet compiler/reference package versions,
checks committed SHA256 pins before extracting or executing them, and compiles
twice in different output directories with `/deterministic+ /nostdlib+`. A byte
comparison is mandatory. It writes the binary and a manifest binding source,
compiler/reference package and executable hashes. Pins were recorded from initial
official HTTPS downloads; they are reproducibility pins, not a publisher signature
or independent supply-chain audit. No compiler or framework is globally installed.
The build output directory and cache must be task-owned scratch directories.

No native token/job component test may run on the active physical host. Only on a
fresh authorized GitHub-hosted disposable Windows runner, run:

```powershell
& C:/task/native-build/StratTester.Native.exe --selftest-native COMPONENT_TESTS_ONLY
if ($LASTEXITCODE -ne 0) { throw 'Native component APIs failed' }
```

The mode requires GITHUB_ACTIONS=true, RUNNER_ENVIRONMENT=github-hosted and
RUNNER_OS=Windows as an operational accident guard. These values are spoofable,
are **not authorization/trust evidence**, and never enable `--launch`. The only
success status is COMPONENT_API_TESTS_PASS, with native_enforcement=false. Tests
create/query/close owned kernel objects and scratch input fixtures, plus one owned
benign sleeping probe child. There are no research children. Local native
component testing is NOTRUN. Hosted results must be bound
to exact source/binary hashes and must not be relabeled sandbox/G1 acceptance.

## Separately reviewed WFP socket component

`--selftest-wfp COMPONENT_TESTS_ONLY` has the same hosted-VM guard and must be
reviewed/invoked separately. It starts owned IPv4/IPv6 loopback listeners and
copies this executable to a unique task-owned probe path. Only that path is
targeted by four terminating block filters at ALE_AUTH_CONNECT and
ALE_AUTH_RECV_ACCEPT (both address families). There are no netsh/firewall-wide
rules, remote servers, credential inputs or changes to the runner executable's
network policy. Policy lives in a dynamic WFP session; session close removes it.

The test requires successful restricted owned-probe connections to BOTH live
listeners before filtering; then queries all four installed kernel filters,
including exact application identity blob; requires WSAEACCES on BOTH connection
attempts; closes the policy session; and requires successful recovery connections
to the same listeners. A missing route, refused port, timeout, lack of WFP access,
or unavailable IPv6 fails the component test. It never counts those as isolation.
Each owned child is created suspended, assigned to the bounded job before resume,
waited with a timeout and cleaned up through its direct handle.

This experiment is **NOTRUN locally**. Its only success label is
WFP_OWNED_SOCKET_COMPONENT_PASS, with native_enforcement=false. It demonstrates
only direct TCP socket policy for the owned executable. It does not verify
incoming receive behavior, UDP, DNS Client service proxy behavior, other executable
identities, full descendant isolation, or all application network mechanisms.
Those remain explicit qualification blockers. `--launch` remains unconditional
BLOCKED regardless of component results. The environment guard is not security
authorization. No network component runs as part of `--diagnose` or the safe unit
tests.

## Separately reviewed inherited handle component

`--selftest-handles COMPONENT_TESTS_ONLY` uses the same hosted-VM-only accident
guard. It locks an owned `abc` fixture, duplicates its read-only handle as
inheritable, and creates a distinct inheritable read/write canary handle. A
STARTUPINFOEX HANDLE_LIST permits only the read-only fixture into an owned
restricted probe created suspended and assigned to its job before resume. The
probe checks `abc`, seeks to byte zero, attempts a one-byte `x` mutation of this
owned disposable fixture and requires WriteFile ACCESS_DENIED,
and verifies that the canary's volume/file identity was not inherited at its
numeric handle value. Successful mutation fails the component test. The parent
independently reopens/hashes the fixture and requires the literal SHA256 of `abc`
and a length of three. This samples correct allowlist configuration and
read-only access, not an exhaustive handle-leak audit.

All owned probe children receive an explicit Unicode environment allowlist:
only SystemRoot/WINDIR, TEMP/TMP and three operational hosted-VM guard values.
PATH, COMSPEC and CI token/credential variables are absent. Each owned child
rejects any environment key outside that allowlist. No parent CI environment
block is inherited. This component and all child creation modes remain NOTRUN
locally and cannot enable research execution.

## Missing mandatory controls

Owner signature/trust verification, restricted SIDs and filesystem confinement,
full filesystem namespace confinement beyond the input handle component, explicit
inherited read-only handle allowlist for research, qualified research child
lifecycle, wall-clock/output limits, and WFP/AppContainer IPv4/IPv6/DNS/loopback egress
confinement are **NOT IMPLEMENTED**. Adversarial process tests and complete native
sandbox enforcement are **NOTRUN**. No fallback subprocess exists. All of these
must be implemented, independently reviewed and verified in disposable Windows
VMs before any research process path can be introduced; physical node execution
also requires separate explicit owner authorization.

## Dependencies and licenses

Build-only Microsoft.Net.Compilers 3.11.0 declares MIT in its NuGet metadata;
source commit ae1fff344d46976624e68ae17164e0607ab68b10. Its package is deprecated,
chosen for task-private .NET Framework compiler compatibility; no support or
security claim is implied. Microsoft.NETFramework.ReferenceAssemblies.net472
1.0.3 points to the [Microsoft dotnet MIT license](https://github.com/microsoft/dotnet/blob/main/LICENSE).
Neither compiler nor reference binaries are shipped with the broker. The
executable requires the already installed Windows .NET Framework runtime.

Win32 contracts: [CreateRestrictedToken](https://learn.microsoft.com/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken),
[AdjustTokenPrivileges](https://learn.microsoft.com/windows/win32/api/securitybaseapi/nf-securitybaseapi-adjusttokenprivileges),
[job limits](https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information),
and [CPU rate](https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_cpu_rate_control_information).

WFP API/layout sources: [FwpmEngineOpen0](https://learn.microsoft.com/windows/win32/api/fwpmu/nf-fwpmu-fwpmengineopen0),
[FWPM_FILTER0](https://learn.microsoft.com/windows/win32/api/fwpmtypes/ns-fwpmtypes-fwpm_filter0),
and Microsoft's [SDK declarations](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/fwpmu.h).
