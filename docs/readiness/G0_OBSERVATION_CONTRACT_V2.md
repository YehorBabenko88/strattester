# G0 observation contract v2 and target facts boundary

Baseline1ab3c807d4a4ed9446cbd2cc84365d7ac5dbbdb4/tree2696d6e55e9f87656dd7f7e6f6d7e95f2efa51b4.
The collector JSON schema remains1 with explicit observation_contract_version2.
This is a source-only diagnostic contract, not physical collection or acceptance.

| State | Meaning | Admission implication |
|---|---|---|
| OBSERVED | Successful nonempty source; required fields present | Provider observation only, not validated truth or independent target identity |
| EMPTY | Successful source returned zero rows | Acceptable emptiness only where observation_requirements.empty_allowed is true |
| MISSING | Nonempty source lacks required properties or valid identity | Required facts absent; blocked |
| UNAVAILABLE | Command/provider failed, including partial pipeline failure | No partial rows admitted; blocked |
| NOT_COLLECTED | Target evidence template has not been observed | Manifest-only sentinel, never emitted as a provider result |

Previously, successful empty TCP/UDP lists were OBSERVED and empty required
hardware was MISSING. This conflated observation cardinality with whether a
required fact exists. v2 always reports EMPTY for successful zero-row results and
records the required-fields/empty_allowed policy separately. Hardware EMPTY
still means required facts are absent. Valid empty listeners do not prove network
isolation. Known provider errors, even an apparent no-match error, stay UNAVAILABLE
unless a separately qualified source contract proves otherwise. No error message
is parsed into invented zero/empty values.

Existing missing/invalid UUID and hostname never produce a host identity hash.
No coercion of unobserved facts, warnings or partial results into PASS is added.
The report always remains BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE, G1 NOT_AUTHORIZED.
Both PowerShell5.1 and7 tests replace all inventory calls. Real CIM/NetTCPIP,
permissions, services and physical targets are not probed by this change.

The separate TARGET_G0_EVIDENCE_MANIFEST.template.json enumerates exact host,
OS/PS/Python/Torch/dependency, resource/GPU, process/port/ACL/source ownership and
hash/receipt slots. Every physical fact is null and NOT_COLLECTED. In particular,
null is not an empty observed list. Real target identities, OS versions, hardware,
credentials or source ownership cannot be copied from the development machine or
synthetic fixtures. The command protocol remains the adjacent read-only template;
release hashes are filled externally after the ZIP is sealed to avoid hash cycles.
Target/tool/fact slots require independently admitted evidence from an owner-
selected disposable VM. LS5/PC4 are protected with no permitted operations.

No actual G0 collection, G1, native sandbox implementation, listener, production
database or service operation is added. The target manifest is not an accepted
receipt, signed owner authority or authorization. Owner-v2 G1 remains separately
unsigned with missing owner/VM/nonce/expiry; all native and external prerequisites
still block admission. GPU driver observation is not real CUDA/PyTorch execution.

## Evidence handling

An independent API test created task-owned .pytest-api-final-cycle-20261027 under
the checkout. Automatic policy rejected its cleanup. It is preserved unchanged;
no deletion retry, alternate shell, move or permission bypass is used. The exact
fixture-only path is explicitly ignored alongside ordinary pytest caches; its
retention and review are recorded outside the source inventory. Actual test raw
stdout and findings are retained as evidence, not hidden or replaced by ignoring
the disposable directory. Final full CI uses the exact committed source and
retains every mandatory/platform node and skipped/deselected result.
