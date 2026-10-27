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

## Declarative reporting schemas and compatibility

[Collector schema](schemas/g0-observation-v2.schema.json) describes existing JSON
`schema=1` with `observation_contract_version=2`.
[Evidence-manifest schema](schemas/g0-evidence-manifest-v1.schema.json) describes
the diagnostic manifest `version=1`, also referencing collector1/observation2.
Both use JSON Schema 2020-12. Version fields are integers; booleans, unknown
versions, missing required fields and unknown top-level fields are rejected.
These schemas document diagnostic formats; they do not extend the collector,
validate physical truth, verify signatures or grant admission.

Schema validation operates on parsed JSON values, not raw bytes. Under standard
JSON Schema semantics, a mathematical integer such as `1.0` satisfies type
integer; the existing inspector additionally rejects it through strict parsed
types. External byte pins, duplicate-key rejection, input budgets and strict
runtime types remain separate checks. A schema result cannot replace them.

Provider output permits OBSERVED, EMPTY, MISSING and UNAVAILABLE only.
NOT_COLLECTED belongs to the manifest template. Manifest NOT_COLLECTED requires
null observed values and receipt hashes. EMPTY requires an actual empty list,
never null. Required hardware EMPTY remains a blocker even though its reporting
shape is valid. OBSERVED/MISSING require nonempty observed structures;
UNAVAILABLE cannot carry partial observed rows. A valid claim of any state
still produces BLOCKED in the existing diagnostic inspector.

Collector provider names and physical manifest groups are different namespaces.
For example, `cpu`/`disk` metadata do not establish resource enforcement, and
`gpu` adapter metadata do not establish real CUDA execution. The collector does
not supply a Python/Torch inventory, independent VM identity, process creation
binding, source ownership or complete ancestor ACL/mount evidence.

Mocked PowerShell5.1/7 tests replace every inventory command. They check array
cardinality, nulls, required fields, error redaction and state reporting against
the declarative schema. They run no real CIM/NetTCPIP/ACL/process inventory.
Compatibility is limited to those mocked outputs; actual Windows provider
behavior, physical controls and target acceptance remain unqualified.

The schema is deliberately stricter than the existing bounded diagnostic
inspector for descriptive fields: descriptions/lists are typed and all exact
reporting fields are required. `command_captures` remains untrusted descriptive
JSON, not validated command policy. No executable qualification, capture or
admission implementation is added by this reporting-only update.

Use [the read-only checklist](G0_READ_ONLY_VM_CHECKLIST.md) and
[ten-group final-report template](G0_FINAL_REPORT.template.md). Every unobserved
physical fact remains NOT_COLLECTED/null. Older physical notes elsewhere in the
repository are historical records, never permission to probe a current host.

## Evidence handling

An independent API test created task-owned .pytest-api-final-cycle-20261027 under
the checkout. Automatic policy rejected its cleanup. It is preserved unchanged;
no deletion retry, alternate shell, move or permission bypass is used. The exact
fixture-only path is explicitly ignored alongside ordinary pytest caches; its
retention and review are recorded outside the source inventory. Actual test raw
stdout and findings are retained as evidence, not hidden or replaced by ignoring
the disposable directory. Final full CI uses the exact committed source and
retains every mandatory/platform node and skipped/deselected result.
