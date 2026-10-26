# Windows native broker: component implementation, research execution blocked

This is compiled Windows x64 managed-native interop source targeting .NET Framework
4.7.2, not a Python launcher or a full sandbox. The executable has **no research
process creation path**. `--launch` always returns JSON BLOCKED and exit 78 before
opening arguments or running commands. No G1 authorization is possible.

Implemented Win32 components, reachable only through the disposable VM component
test mode:

* Duplicate the current process token using `CreateRestrictedToken`, remove all
  remaining privileges using `AdjustTokenPrivileges(SE_PRIVILEGE_REMOVED)`, then
  independently query the token privilege count and require zero. No token is
  assigned to any process; group SIDs and filesystem access are not confined.
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
  No caller-provided executable, script or research workload can be launched.

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
