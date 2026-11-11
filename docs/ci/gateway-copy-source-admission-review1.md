# Gateway canonical test-owned source copy

Baseline: 0c4f64c897aacd78bbec0e1faa886c7003c353ff, tree
064ed4b7661fce976f0fd97b236e85d2ebfff7f0. This successor is source-only;
no calculation, imports, compilation, tests or CI of this successor performed.

Original run 42929428724, Windows job 130224124675, executed 38 tests and
failed `test_source_changed_after_calculation_refused`: mutation observer did
not set `changed`. Ubuntu job succeeded. This does not identify the earlier
refusal code or failing production admission stage. A Windows path alias is
an unproven hypothesis. PR79 original run43041826648 then observed an early
COPY_POSITIVE_CALIBRATION/SOURCE_UNAVAILABLE with canonical_identity_equal=false
and ordinary ancestry/single links/pins=true. The production canonical-identity
guard correctly refused that fixture spelling. The underlying alias mechanism
remains UNKNOWN. Original RED and immutable hosted47 evidence remain intact.

Ownership: only this document and tests/gateway_adapter/{support.py,
test_gateway_adapter.py}. Production adapter, workflow, existing 38 test IDs,
timeouts, source pins and guards remain unchanged.

The mutation test first performs a positive calculation on the exact same copied
directory, before installing its profile observer or mutating any bytes. It
compares the artifact to the pinned reference and checks execution authority is
false. A failure reports a closed error code and fixed phase, plus boolean source
facts. It does not retry with a resolved path or change admission rules.

Before copying any source bytes, copy_source validates the existing new empty
TemporaryDirectory's lexical ancestry root-first as ordinary directories without
links/reparse points. Only then it resolves strictly, validates the canonical
ancestry again, requires known nonzero dev/ino to match the original directory,
and rechecks lexical identity. Unknown or differing identity is DENY. It selects
that spelling before any application call. Exclusive src/package/file creation
does not overwrite, move or delete existing data. The record is TEST-ONLY and
the mutation test asserts its booleans and canonical equality. Actual app source
admission and positive calculation still run independently; no caller/runtime/API
input normalization or fallback after app refusal is introduced.

Diagnostic facts expose only absolute/canonical-identity equality, all-three-pin
equality and ordinary-single-link checks; failures expose a bounded class label.
No path, account, source bytes, exception message or credentials are printed.
These observations are diagnostics, not a substitute for production admission;
the production adapter still independently checks ancestry and raw identity.

If calibration succeeds, the observer matches both function name and exact
copied adapter filename, records entry, then mutates only the owned copy on
return. Existing mutation assertion remains; the refusal must specifically be
SOURCE_UNAVAILABLE. The previous profile hook is restored in finally.

Future execution requires a separate allocation. First preserve its original
result, including calibration refusal if any; do not weaken assertions, suppress
tests or alter production code based on the path-alias hypothesis. Any later fix
needs proven cause and exact ownership approval. Rollback: discard this separate
three-file successor; baseline0c4f/PR79 and889hosted47 evidence are untouched.
