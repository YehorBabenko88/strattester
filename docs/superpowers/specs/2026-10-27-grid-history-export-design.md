# Grid history exporter hardening

## Intent and constraints

Extend the existing sealed-history exporter on PR #21, refreshed at
`f60869686a51693799b4844a1af49c9b39ba45d5`, on branch
`parallel/grid-history-export`. The user selected strengthening the existing
implementation. Native Grid latest-state export remains BLOCKED. No production
database access, main merge, G1, or trading is authorized by this work.

Fresh remote Grid main is `d537d525296ef34f727996e240ae6c60102c6082`.
The three DDL fixture source blobs and eight producer assessment blobs match
their existing SHA256 pins when read as Git object bytes (Windows checkout
line endings are not source-object evidence).

## Approaches

The selected approach extends `financial_grid_exporter`, its existing consumer
manifest schema and Ed25519 test signer. This preserves interoperability and
the explicit separation between sealed producer assertions and native truth.
A separate exporter would duplicate the trust boundary. Deriving historical
availability or revisions from latest-state rows is excluded by requirements.

## Proposed changes

1. Audit native PostgreSQL baseline/migrations, legacy SQLite test DDL, shard
   membership, candle/footprint overwrite, WAL retention, availability and
   consumer-watermark producers. Record exact source identities and missing
   first-knowledge/revision/completeness/coherence facts. Recognizing a test DDL
   does not establish any deployed SQLite schema.
2. Harden sealed PostgreSQL reads against name resolution, views, RLS,
   inheritance, schema drift and concurrent relation/namespace replacement.
   Use a pinned catalog search path, bounded catalog inspection, read-only
   repeatable-read transactions, lock/statement timeouts, verified ordinary
   relation identities and queries that cannot execute replacement views.
   Reject unqualified physical identity before payload evaluation. Apply the
   same fail-closed principle to SQLite schema objects as evidence warrants.
3. Keep external source seals, exact membership, retained revision sequence,
   first availability, routing and shared epoch mandatory. No inferred history.
4. Preserve signed consumer compatibility and the public RFC test key's
   synthetic-only restriction. Test manifest/snapshot/source binding, tampering
   and replay. Do not invent a production key or claim producer authority.
5. Add deterministic concurrent tests using independent connections against
   newly owned SQLite WAL databases and an ephemeral loopback PostgreSQL
   cluster. Reuse existing owned-cluster shutdown helpers; never discover or
   manage an installed database service. Include sharded coherence rejection.

## Validation and delivery

First reproduce each defect with a failing test, then run focused exporter,
native capabilities/readiness, signed consumer and snapshot regressions.
Run a dedicated hosted CI selection with PostgreSQL and signing prerequisites;
retain skipped/blocked/failed results separately. Avoid workflows that perform
G1, native physical admission or trading. Review the final diff independently.

Create a Draft PR, preferably against PR #21's integration branch to isolate
this change. Bind evidence to the exact pushed commit and tree, refreshed
source HEADs, test commands/results, CI job/run URLs and SHA256 artifact hashes.
Evidence inside a commit identifies its code parent/tree without pretending to
contain its own future commit hash. Final external evidence can bind the exact
commit without a hash cycle. Report P0/P1/P2 and remaining readiness blockers.

## Builder decisions and limits

The implementation language and test tools remain Python/pytest/psycopg and
the existing pinned OpenSSL verifier. Signing proves origin under the configured
key, not completeness or historical truth. Hostile filesystem namespace races
and physical durability remain separate qualifications. Native historical
readiness stays blocked even when engineering tests pass.
