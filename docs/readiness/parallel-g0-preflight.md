# Parallel G0 preflight software component

Baseline: f60869686a51693799b4844a1af49c9b39ba45d5.

`strattester.research.financial_g0_preflight.inspect_g0_preflight(selection, capture)`
is a pure library API for already parsed private selection and capture-plan
mappings. It reports every absent declared prerequisite by field name, distinguishes
invalid capture bounds/local tool paths/digests, and labels present claims
unverified. No file, target, tool, receipt, storage namespace or signature is opened
or executed. Private values are never copied into its report. Inputs are unchanged.

Both input envelopes must retain their existing nonauthorizing states. The result
always remains G0 BLOCKED, G1 Execute/Cleanup NOT_AUTHORIZED, Deployment/Trading
NO-GO. Even all fields populated or hash-shaped receipts cannot admit G0 or G1.
This checks declaration presence and limited syntax; it does not validate UUIDs,
SIDs, target identity, ownership, signatures, replay, ACLs, storage or enforcement.
Other unconsumed fields do not acquire validation or authority from this API.

Current facts remain VM NOT_SELECTED, provider/UUID/owner NOT_COLLECTED, sandbox
and evidence paths NOT_AUTHORIZED, private delivery NOT_DEFINED and rollback
NOT_VERIFIED. No inventory was run against a target. The inventory script is
unchanged; existing contract tests use software fixtures.

Lead integration required: CLI command, research package roster and gate/test
manifest wiring are intentionally reserved and unchanged. No automatic execution
or admission should be added when wiring this inspection API.

Validation: initial absent-module collection error, then explicit missing-function
RED (22 failed), then GREEN (22 passed). Expanded missing-field coverage: 47 passed,
0 failed/skipped/deselected. A first broader run had 22 passed and 124 fixture setup
errors because the external temporary parent did not exist; this was a harness
setup failure and is retained separately from corrected reruns. All runs use the
existing financial-venv Python with OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1 and
fresh explicit --basetemp directories under work/external-evidence. No install.

Corrected broader G0 run: 146 passed, 0 failed/skipped/deselected in 101.27s,
covering the first 22 new cases plus existing evidence inspection, signed receipt,
and PowerShell inventory contract fixtures. The full repository pytest run is
recorded separately in the external evidence log.
