# Native v4 independent read-only review

Reviewed HEAD `f92d6947891190b92380215f696150ad6e550643` (PR31 final/native-build). Scope: all three native/windows/*.cs files, README, scripts/build_windows_native.py and tests/native/test_native_build.py. No component APIs, child probes or networking tests were executed by this reviewer on LS5. Existing safe-test/build artifacts were read and hashes independently compared.

## Decision

No concrete P0/P1 defect found that blocks a first **separately authorized disposable GitHub-hosted Windows component run** of this exact source. This is source-review clearance, not user authorization, execution approval, security certification or sandbox acceptance. Research `--launch` remains unconditionally BLOCKED before parsing paths/commands; filesystem namespace isolation, owner verification, DNS service proxy and complete native sandbox enforcement remain missing. Hosted component execution has not been observed by this reviewer.

## Source and artifact identity

| File | Git blob |
|---|---|
| native/windows/Broker.cs | 162afb9a19d3d8fe43d95a4da291aff2d0112b2a |
| native/windows/HandleComponent.cs | 5f60d6952a740eb049ceb0103b31f2d792010a8a |
| native/windows/WfpComponent.cs | 829496c6d7f90c9a9165c625364f7a8ba27ee0fb |
| native/windows/README.md | 4aafbd22498246e5b6a8ebd9cc725421d6139727 |
| scripts/build_windows_native.py | 3e925a912d4a9084273fba5f572bdd410d43574a |
| tests/native/test_native_build.py | 6fb1978e116a2475224fd3c5075d33645c1be80b |

Existing work/native-toolchain/build-v4/StratTester.Native.exe SHA256 independently recomputed: `7d2e35d86cb7f4dc5de6a570a111a4a61761da07db232e77e14e9f932b2719f9`, matching its manifest. All three source hashes in manifest independently matched git-show bytes at reviewed HEAD. Existing safe-tests-v4.txt reports 12 tests, OK, 2 skipped (hosted junction fixture and unavailable directory-symlink privilege). Reviewer did not rerun native modes, build, or safe tests; this distinction avoids claiming another independent execution.

## Reachability and side effects

- `--diagnose`: only current-process job membership and executable hashing. No token/job creation, child, policy, service or network operation.
- `--launch`: unconditional denial, including arbitrary trailing arguments; it never reads caller paths or creates a process.
- `--selftest-native`, `--selftest-wfp`, `--selftest-handles`: exact COMPONENT_TESTS_ONLY argument and all three hosted environment variables required. Guard is spoofable and explicitly an accident guard, not authority. Refusal tests remove all three variables.
- Owned sleeping/network/handle probe entry points also require HostedVm plus minimal environment; they remain internal experiments, not research launch. Network mode accepts loopback ports only, no remote addresses. Handle mode accepts numeric inherited handles only. Do not set spoofed hosted variables locally.
- No netsh, firewall-wide configuration, service installation/start/stop, ACL rewrite, registry modification or production DB access found. The hosted junction unit fixture uses mklink only within owned temporary directories and removes only its junction.

## Child ownership and cleanup

Every create path targets only the executing assembly or its GUID-directory copied image; no caller executable/script/working directory is accepted. CreateProcessAsUser uses CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT and no-window flags. Each child is assigned and queried in its owned bounded job before resume. Error paths call TerminateProcess through returned direct child handle, wait, then close thread/process handles; jobs are disposed. Kill-on-close probe disposes job and checks exit separately. Kill/wait cleanup return values are not asserted in finally, so cleanup is best-effort on unexpected kernel failure; this is not full lifecycle enforcement evidence.

Restricted tokens use DISABLE_MAX_PRIVILEGE then explicit SE_PRIVILEGE_REMOVED for all remaining entries, and a component test queries zero privileges. No restricting SID or admin-group disabling is claimed; this token alone is not a filesystem/security sandbox. CPU/memory/process/job flags and query values are internally consistent. Runtime limit effectiveness and child effective token identity still require independent tests.

Explicit environment block is sorted, Unicode and double-NUL terminated (StringToHGlobalUni adds the second terminator). It contains only seven declared keys; no PATH, COMSPEC or CI secrets. Child rejects undeclared keys. Windows and TEMP values are derived from the authorized hosted parent, not arbitrary CLI input. Handle-list path uses inheritable duplicates, bInheritHandles=true, STARTUPINFOEX size, attribute-list flag and only the read-only input handle; the separate inheritable canary is deliberately omitted. Canary test is a single numeric identity check, not exhaustive handle enumeration.

## WFP scope, ABI and teardown

Only the unique GUID-directory copied probe image is passed to FwpmGetAppIdFromFileName0. Each of four filters has one exact app-ID equality condition and terminating block action; none targets runner executable, all apps or external identity. Layers are ALE_AUTH_CONNECT v4/v6 and ALE_AUTH_RECV_ACCEPT v4/v6. Listeners bind only owned IPv4/IPv6 loopback ephemeral ports. Baseline/blocked/recovery use the same listeners and require explicit access denial for both families rather than treating timeout/refusal as success. Receive/accept behavior itself is not tested.

Dynamic session flag 1, nonpersistent filters, fresh sublayer/filter GUIDs. Constructor failure disposes engine; successful test closes before recovery; session close provides automatic object teardown. Dispose zeroes engine before checking close result: an exceptional close failure has no retry handle, although process exit ends dynamic session. This is a nonblocking hardening opportunity for disposable tests, not verified cleanup under arbitrary kernel faults.

Interop declarations were compared with Microsoft FWPM_FILTER0/FWPM_SESSION0 and HANDLE_LIST documentation. x64 layouts Filter=200, Condition=40, Session=72 and runtime guard are consistent; pointer-sized FWP_VALUE and 16-byte context union are represented. Native BOOLs and CreateSymbolicLink one-byte BOOLEAN are correctly marshaled. This is static ABI review; hosted APIs remain NOTRUN here.

Sources: [FWPM_FILTER0](https://learn.microsoft.com/en-us/windows/win32/api/fwpmtypes/ns-fwpmtypes-fwpm_filter0), [FWPM_SESSION0 dynamic-session semantics](https://learn.microsoft.com/en-us/windows/win32/api/fwpmtypes/ns-fwpmtypes-fwpm_session0), [HANDLE_LIST requirements](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).

## Builder and packages

Verified local cached nupkg SHA256 equals both committed pins: Microsoft.Net.Compilers 3.11.0 `e4a540a9cb41d15e6e1cc05fa2cadb847454df9ebe49d683cded2780506ef880`; Microsoft.NETFramework.ReferenceAssemblies.net472 1.0.3 `ffa0a5570a39f911399164d0581ffddef99b5e3dfbaa5f220e5ce22969bcf57c`. Metadata read directly from those verified archives: compiler MIT expression and deprecated-package notice, references licenseUrl Microsoft/dotnet LICENSE. README accurately calls these reproduction pins rather than independent publisher provenance.

Compiler executes only after archive hash verification/re-extraction. Zip escape check uses resolved containment; compiler references explicitly mscorlib/System with /nostdlib, x64, deterministic, warnings-as-errors. Two outputs compared bytewise, all C# source hashes recorded. This demonstrates repeatability within the build invocation; independent clean-machine/repository-root relocation rebuild still requires its own evidence. No global install.

Recursive cache deletion resolves and checks a direct child of intended cache, rejects root/outside/symlink/reparse/non-directory. It uses native Python rmtree, no cross-shell delete composition. Task-owned scratch cache remains required; this path check is not a hostile concurrent-filesystem transaction guarantee. Existing portable tests cover outside/root/corrupt/zip-escape/ordinary child; hosted junction and symlink behavior must be recorded distinctly. Temporary output cleanup also relies on task-owned output root.

## Nonblocking findings and scope limits

1. README first token bullet says “No token is assigned to any process,” while owned child code assigns the privilege-removed token. Fix wording to say no token is assigned to a research process. Broker PreparedComponents comment also says no process creation/job assignment occurs “here”; clarify helper-vs-component distinction.
2. Add native layout offsets for all used structs to future ABI evidence; current WFP size guards alone do not verify each offset or other Win32 structs.
3. Record cleanup failures explicitly in future negative-path tests rather than ignoring final TerminateProcess/Wait/Close return codes; no evidence currently proves forced-error cleanup.
4. Preserve component-only labels. WFP tests direct TCP/owned image only, handle test samples one canary, locked handles exclude preexisting writable mappings only by documented limitation. None supports full sandbox/G1 claims.

No local component execution, G1, install, services, ACL/firewall change, production DB or merge performed. No review approval here overrides pending owner authorization.
