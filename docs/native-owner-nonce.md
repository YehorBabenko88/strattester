# Native persistent owner nonce claims

`OwnerNonce.Claim(ledgerRoot, nonceHex64, authorizationSha256)` consumes an owner
authorization nonce before admission. Call it only after verifying the owner
signature and binding the exact canonical authorization hash. Return means the
receipt has been written, flushed and read back through its retained handle; it
does not authorize admission, resume a process, or establish resource enforcement.

The ledger must already exist on local fixed NTFS storage. Its canonical DOS path
must be at most 160 characters, have ordinary components, and contain no UNC,
device namespace, stream, traversal, control-character, reserved-device or trailing
dot/space aliases. Nonce and authorization identifiers are exactly 64 lowercase
hex characters. These checks occur before filesystem access.

The ledger owner must be the broker's current user, SYSTEM or Administrators. Its
DACL must be protected and contain an explicit current-user full-control grant.
Every effective allow entry must identify only the current user, SYSTEM or
Administrators; unknown, conditional and object-specific ACE forms fail closed.
Null DACLs fail closed. Ancestors may grant other principals ordinary read/traverse
or create-sibling rights, but cannot grant them delete-child, delete, write-DAC,
write-owner, write-attributes, generic-write or generic-all rights. This prevents an
untrusted parent-directory writer from removing the ledger between claims. The
component validates the existing ACL and never silently repairs it. Provisioning
and long-term protection of the ledger are trusted broker/administrator duties.
The LPAC worker receives no SID or capability grant on the ledger or its receipts.

The drive root and each canonical ancestor/root remain open without write/delete
sharing for the entire claim. Each descent uses a single relative component under
the retained parent with `NtCreateFile`, `OBJ_DONT_REPARSE` and
`FILE_OPEN_REPARSE_POINT`, followed by disk/type/reparse/final-name checks on the
returned handle. Receipt creation uses the pinned root as `RootDirectory` and
`FILE_CREATE`, an explicit protected descriptor, synchronous I/O and write-through.
It never checks existence and then creates by a reconstructed path. No existing
object is opened, reused, truncated, replaced or deleted, even if it is an empty
receipt, partial receipt, directory, reparse point or hardlink. New receipts must
have one link and the same volume as the retained root.

An empty claim is flushed first, then the bounded ASCII receipt binds the nonce to
the canonical authorization SHA256. A complete write, second flush, length/security
check and byte-for-byte readback are required for success. Any exception after
creation leaves the nonce consumed. There is no unclaim, retry-overwrite, rollback,
expiry recycling or production cleanup API. Concurrent attempts at the same nonce
can have at most one successful creator. Trusted owners/administrators can still
destroy storage or change ACLs outside this protocol; that privilege is outside the
LPAC worker boundary. `FlushFileBuffers` and write-through are requested durability
controls, not evidence that a physical storage device survives every power fault.

`OwnerNonce.SelfTest()` checks the hosted-Windows guard before choosing fixture
paths. Root wires the guarded `--selftest-owner-nonce COMPONENT_TESTS_ONLY` CLI path.
Only there, disposable owned fixtures exercise replay refusal, eight simultaneous
claims with one winner, empty/partial tombstones, a pinned-directory rename attempt,
root-relative creation after changing the current directory, traversal rejection,
hardlink/reparse aliases, unsafe ACLs and malformed identifiers/paths. Two fixture
helper processes use the same NT create/flush functions and are forcibly terminated
after reporting a persisted empty or partial receipt; their nonces remain consumed.
Those helper processes are component fixtures, never research or trading workers.
All fixtures, claims, hardlinks and junctions remain preserved after the test,
including failure paths. No automatic cleanup or recursive deletion runs. A bounded,
flushed `cleanup-manifest.json` records the fixture path, test result and manual
review requirement. Internal `LastFixture` and `CleanupManifestSHA` fields let the
guarded broker report the exact artifact path/hash for collection. Collect the
manifest and explicit regular receipt files without traversing the preserved
junction; fixture cleanup requires separate resolved-path/reparse review.

On the physical development host, tests only compile twice, invoke malformed values
that fail before native filesystem access, check the hosted guard, and run existing
safe CLI refusal/diagnostic tests. No successful nonce claims, native filesystem
attack probes, hosted-variable spoofing, real owner keys or physical G1 runs occur
there. Until the hosted selftest passes, NT/ACL/runtime behavior remains unverified
on an actual Windows filesystem. A hosted result is component evidence, not full
native admission or sandbox qualification.

API references: Microsoft's [NtCreateFile contract](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)
defines relative `RootDirectory` and `FILE_CREATE` behavior; its
[buffer flushing documentation](https://learn.microsoft.com/en-us/windows/win32/fileio/flushing-system-buffered-i-o-data-to-disk)
describes explicit `FlushFileBuffers` persistence requests.
