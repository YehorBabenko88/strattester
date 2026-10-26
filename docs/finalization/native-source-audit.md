# Independent native source audit

Audit date: 2026-10-26. Integration HEAD: `5d715987d03d4a26d31a48e9767697bbd171cd33`. PR30/source HEAD: `7b424b8161e430351ba265d8ccf9fe1227791bb5`. Common base: `67301726d250973602b964adabdb9eb8d50d0f13`.

Verdict: source contains a deliberately non-executing admission prototype. A verified native launcher, reproducible broker build, binary SHA tied to an artifact, independent verifier and Windows enforcement are absent. Do not describe importing these files as integrating native execution. Native execution remains BLOCKED/NO-GO.

## Exact own-delta

Eight added files, 401 lines relative to common base; no implementation outside this own-delta is implied. All source was inspected via git show and copied to a disposable isolated package for offline tests. Root tracked files and source branch were not edited.

| File | Git blob |
|---|---|
| .github/workflows/windows-sandbox-admission.yml | 83ff37aea21e77bf52b397508ec14b1b3018bc67 |
| strattester/research/windows_native_evidence.py | 76b3f936be5b9b952c6ef6c645c25d4dfaa1af55 |
| strattester/research/windows_native_launcher.py | d9de3ccc5e2e75b96bbdf6503609e6bb54872be6 |
| strattester/research/windows_native_sandbox_admission.py | ebeec0deeab3ceb0a4f80f188cd2381b9c09a6a3 |
| tests/research/test_windows_native_evidence.py | 828252a45be02622c3fda7dffe2b7397695a9349 |
| tests/research/test_windows_native_launcher.py | 18e606bc446c7c3f17e713c44af4699a877b3379 |
| tests/research/test_windows_native_sandbox_admission.py | 89e480f06d3f768eaa73a99532c3bda5a6443e12 |

## Capability matrix

| Capability | Actual source behavior | Evidence status |
|---|---|---|
| Process launcher | validates arguments, then always raises SandboxDenied | implemented denial only |
| Restricted token/privilege removal | enum names and plan text | NOT IMPLEMENTED |
| Suspended create/job-before-resume/kill-on-close | enum names and plan text | NOT IMPLEMENTED |
| CPU/RAM/process tree/time/output limits | integer policy validation only | NO OS ENFORCEMENT |
| Handle inheritance/filesystem confinement | lexical path filter only | NO HANDLE ENFORCEMENT |
| IPv4/IPv6/DNS/loopback egress | enum names and plan text | NOT IMPLEMENTED |
| Capability attestation | rejects even all-true dictionary | denial guard only |
| Evidence receipt | schema checks; only BLOCKED/false/false accepted | no signature or verifier |
| Binary/policy hashes | checks 64 lowercase hex characters supplied by caller | no build/binary identity verification |
| Static evidence hash | bounded read/hash with regular-file check | bugs/limitations below |
| Reproducible native build | no compiler/linker/build or binary artifact in own-delta | ABSENT |
| CI | Python compile + pytest, Windows/Linux, Python 3.11/3.13 | no native build or physical acceptance |

## Bounded local test coverage

Python from existing sibling financial-venv; exact copied source modules and tests under `work/final-native-source-fixture`, isolated empty package initializers. Command: `python -m pytest -q -o addopts= tests --basetemp=pytest-disposable --junitxml=native-source-results-bounded.xml`.
Result: **41 passed, 4 failed, 1 skipped**, 0.23 seconds. Symlink test skipped because privilege unavailable. Earlier first run had 3 setup errors from preexisting default TEMP pytest directory access; rerun used only scratch basetemp and resolved setup errors. This is portable static testing on the current Windows host, not native sandbox/G1 testing or GitHub Actions verification.

Failures:
1. `test_missing_evidence_file_fails_closed`: exact-type Path guard rejects WindowsPath before expected open failure.
2. `test_evidence_file_hash_and_size`: same guard prevents valid pathlib fixtures from hashing. `Path()` returns WindowsPath on Windows and PosixPath on Linux, neither has exact type Path.
3-4. Two unsafe-path test vectors contain literal `\\x00` and `\\x01` path components, rather than actual control bytes. Those legal components pass; real NUL/SOH were separately confirmed denied.

## Disposable RED probes and limitations

No model/process sandbox was launched. Only disposable static files were touched.

- Confirmed: hash_static_evidence_file accepts string `ads-disposable.txt:probe` and hashes its alternate stream (`ADS_HASH_ACCEPTED True`). Thus this helper does not reject ADS/device/junction hazards merely because the separate lexical filter does. If evidence policy requires a regular base file, this is a concrete bypass. It does not authorize execution because all execution gates deny.
- Lexical probe `C:\safe\COM¹.txt` accepted; Windows DOS superscript device aliases are not covered by ASCII COM1..9/LPT1..9 list. Native handle validation remains mandatory; this probe itself opened no device.
- Windows lacks os.O_NOFOLLOW in this implementation; path.is_symlink() before os.open is not atomic. Parent junction/reparse traversal is not rejected. No TOCTOU claim was tested or proven safe.
- Receipt hashes are caller-supplied strings and need not match any actual binary or policy; currently harmless to execution authorization because PASS and native_enforcement=True are denied.

## Safe portable imports and blockers

Safe candidates are policy numeric validation, lexical prefilter explicitly labeled non-authoritative, unconditional denial launcher, unconditional capability denial and receipt schema checks restricted to BLOCKED. Correct Path exact-type support using trusted concrete pathlib types (without admitting arbitrary __fspath__), correct control-byte tests, retain no-process guarantee, and add bounded fixture tests for ADS and parent-reparse behavior before importing evidence hashing. A simpler safe static helper could accept strings only and explicitly deny unsupported filesystem semantics; do not market it as native confinement.

Do not import stale full source tree or treat enum declarations as controls. CI should publish JUnit and document portable-only scope; its present tests fail locally and it has no native compilation, deterministic rebuild comparison, signed receipt, binary download/check or OS adversarial tests. A real native implementation requires separately reviewed broker source/build, independent binary/policy trust binding, disposable Windows VM enforcement evidence and owner authorization. No G1, install, services, ACL/firewall, production DB, or main merge was performed. Truncated Owner-sign instructions were not treated as authorization.
