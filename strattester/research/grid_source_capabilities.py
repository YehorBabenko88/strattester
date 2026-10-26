"""Bounded observations of native Grid catalogs, never historical export receipts.

The recognized PostgreSQL shape is latest state. An ingestion timestamp on raw
events and available_ts on derived levels do not recover candle revisions or
first availability. A catalog hash covers metadata, never market rows. Matching
migration names are observed claims, not proof that SQL ran or history survived.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import sqlite3
import time

from .financial_grid_exporter import _explicit_postgres_parameters
from .financial_signed_export import identity
from .financial_snapshot import canonical_bytes, reject_linked_path
from .grid_producer_readiness import GRID_SOURCE_COMMIT


@dataclass(frozen=True)
class NativeGridSource:
    source_id: str
    engine: str
    location: str


@dataclass(frozen=True)
class NativeGridCatalog:
    source_id: str
    engine: str
    catalog_sha256: str
    catalog_rows: int
    adapter: str
    migration_lineage: str
    migrations: tuple[tuple[int, str], ...]
    observed_fields: tuple[str, ...]
    missing_facts: tuple[str, ...]
    source_commit: str = GRID_SOURCE_COMMIT  # Audit baseline, not deployment identity.
    status: str = 'BLOCKED'
    eligible: bool = False
    evidence_kind: str = 'READ_ONLY_CATALOG_OBSERVATION'
    coherence_epoch_id: None = None
    data_seal_sha256: None = None

    def to_dict(self):
        return asdict(self)


_MISSING = (
    'first_availability_history', 'retained_revisions', 'cross_source_coherence',
    'market_partition_authority', 'source_completeness_receipts',
    'producer_issued_immutable_export', 'physical_schema_identity',
    'deployed_producer_identity',
)
_LEGACY = (
    ('symbol', 'TEXT', 0, 1), ('ts', 'INTEGER', 0, 2),
    ('open', 'TEXT', 0, 0), ('high', 'TEXT', 0, 0), ('low', 'TEXT', 0, 0),
    ('close', 'TEXT', 0, 0), ('volume', 'TEXT', 0, 0), ('turnover', 'TEXT', 0, 0),
)
_POSTGRES = {
    'candles_1m': (
        ('symbol', 'text', True), ('ts', 'timestamptz', True),
        *((n, 'numeric', False) for n in ('open', 'high', 'low', 'close', 'buy_volume', 'sell_volume', 'delta')),
        ('trade_count', 'int4', False), ('poc_price', 'numeric', False),
        ('extra', 'jsonb', True), ('quality_status', 'text', True), ('quality_reasons', 'jsonb', True),
    ),
    'footprint_1m': (
        ('symbol', 'text', True), ('ts', 'timestamptz', True), ('price', 'numeric', True),
        *((n, 'numeric', False) for n in ('buy_volume', 'sell_volume', 'delta', 'volume')),
        ('buy_count', 'int4', False), ('sell_count', 'int4', False), ('extra', 'jsonb', True),
    ),
    'market_events': (
        ('id', 'int8', True), ('symbol', 'text', True), ('event_ts', 'timestamptz', True),
        ('event_type', 'text', True), ('source', 'text', True), ('payload', 'jsonb', True),
        ('ingest_ts', 'timestamptz', True),
    ),
    'schema_migrations': (('version', 'int8', True), ('name', 'text', True), ('applied_at', 'timestamptz', True)),
}
_PRIMARY_KEYS = {
    'candles_1m': ('symbol', 'ts'), 'footprint_1m': ('symbol', 'ts', 'price'),
    'market_events': ('id',), 'schema_migrations': ('version',),
}

# Exact version/name lineage of grid/migrations.py at GRID_SOURCE_COMMIT.
_MIGRATIONS = (
    (1, 'baseline_jsonb_extensible'),
    (2, 'market_microstructure_tables'),
    (3, 'minute_data_quality'),
    (4, 'market_features_1m'),
    (5, 'volatility_regime_columns'),
    (6, 'poc_lifecycle'),
    (7, 'historical_level_events'),
    (8, 'historical_level_availability'),
    (9, 'level_event_idempotency'),
    (10, 'observer_recovery_state'),
    (11, 'ml_event_samples'),
    (12, 'ml_orchestrator_concurrency'),
    (13, 'ml_artifact_lifecycle'),
    (14, 'ml_lifecycle_registry'),
    (15, 'immutable_dataset_membership'),
    (16, 'consumer_safe_retention_and_control_state'),
    (17, 'integrity_repair_state'),
    (18, 'ml_fencing_immutable_payloads_and_label_horizon'),
    (19, 'ml_job_deduplication'),
    (20, 'ml_resource_reservations'),
    (21, 'markov_transition_edge_results'),
    (22, 'strategy_comparison_results'),
    (23, 'historical_experiment_runs'),
    (24, 'cold_start_backfill'),
    (25, 'market_data_capabilities'),
    (26, 'archive_compaction_manifests'),
    (27, 'trade_archive_discovery'),
    (28, 'legacy_bootstrap_import'),
    (29, 'legacy_symbol_import_state'),
    (30, 'required_retention_consumer_registry'),
    (31, 'derived_minute_completion'),
    (32, 'pilot_bootstrap_state'),
    (33, 'telegram_update_idempotency'),
    (34, 'microstructure_research_capture'),
    (35, 'hot_table_autovacuum_policy'),
    (36, 'micro_agent_research'),
    (37, 'scientific_hypothesis_memory'),
    (38, 'durable_scientific_outcomes'),
    (39, 'scientific_source_event_fencing'),
    (40, 'scientific_pattern_mining'),
    (41, 'scientific_simulation_promotion_gate'),
    (42, 'historical_scientific_bootstrap'),
    (43, 'system_lifecycle_orchestration'),
    (44, 'scientific_method_plugins'),
    (45, 'scientific_simulation_attempt_fencing'),
    (46, 'scientific_method_event_idempotency'),
)


def inspect_native_grid(source, *, max_catalog_rows=2048, max_bytes=1048576,
                        cancel=lambda: False):
    """Read catalog metadata and at most 47 migration claims from an explicit source.

    No market table is read. No file is created, copied, checkpointed, migrated,
    or sealed. Engines get independent read transactions; this API never infers
    a cross-store epoch. Native export remains blocked even for recognized DDL.
    """
    for value, ceiling in ((max_catalog_rows, 2048), (max_bytes, 1048576)):
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError('catalog allocation budget')
    if type(source) is not NativeGridSource:
        raise ValueError('explicit native source required')
    identity(source.source_id)
    if source.engine not in ('sqlite', 'sharded_sqlite', 'postgresql'):
        raise ValueError('unsupported native source engine')
    if type(source.location) is not str or not 1 <= len(source.location) <= 4096:
        raise ValueError('explicit native source location required')
    started = time.monotonic()

    def check():
        if cancel(): raise RuntimeError('cancelled native Grid catalog inspection')
        if time.monotonic() - started > 5: raise ValueError('catalog time budget')
        return 0

    check()
    rows = []
    byte_count = 0

    def add(kind, values):
        nonlocal byte_count
        check()
        row = (kind, *values)
        if len(rows) >= max_catalog_rows: raise ValueError('catalog row budget')
        size = len(canonical_bytes(row))
        if size + byte_count > max_bytes: raise ValueError('catalog byte budget')
        byte_count += size
        rows.append(row)

    if source.engine in ('sqlite', 'sharded_sqlite'):
        adapter, lineage, migrations, fields = _sqlite(source, check, add, max_catalog_rows)
    else:
        adapter, lineage, migrations, fields = _postgres(source, check, add, max_catalog_rows)
    check()
    missing = _MISSING + (('unrecognized_catalog_shape',) if adapter == 'UNRECOGNIZED' else ())
    return NativeGridCatalog(source.source_id, source.engine,
        sha256(canonical_bytes(sorted(rows, key=canonical_bytes))).hexdigest(), len(rows),
        adapter, lineage, migrations, fields, missing)


def _sqlite(source, check, add, row_limit):
    path = reject_linked_path(source.location)
    con = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, isolation_level=None, timeout=1)
    try:
        con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 16384)
        con.execute('PRAGMA query_only=ON')
        con.execute('PRAGMA trusted_schema=OFF')
        con.set_progress_handler(check, 1000)
        con.execute('BEGIN')
        objects = con.execute('''SELECT type,
            CASE WHEN length(CAST(name AS BLOB))<=256 THEN name END,
            CASE WHEN length(CAST(tbl_name AS BLOB))<=256 THEN tbl_name END,
            CASE WHEN length(CAST(coalesce(sql,'') AS BLOB))<=8192 THEN coalesce(sql,'') END
            FROM sqlite_schema ORDER BY type,name LIMIT ?''', (row_limit+1,))
        tables = {}
        for kind, name, table, sql in objects:
            if name is None or table is None or sql is None:
                raise ValueError('catalog cell budget')
            add('object', (kind, name, table, sql))
            if kind != 'table': continue
            columns = []
            for _, column, datatype, nullable, _, pk, hidden in con.execute(
                    'SELECT * FROM pragma_table_xinfo(?) LIMIT ?', (name, row_limit+1)):
                if len(column.encode()) > 256 or len(datatype.encode()) > 256:
                    raise ValueError('catalog cell budget')
                add('column', (name, column, datatype, nullable, pk, hidden))
                columns.append((column, datatype.upper(), nullable, pk))
            tables[name] = tuple(columns)
        recognized = tables.get('candles') == _LEGACY
        return ('GRID_LEGACY_CANDLES_SHAPE_V1' if recognized else 'UNRECOGNIZED',
                'NOT_APPLICABLE', (), ())
    except sqlite3.OperationalError:
        check()
        raise
    finally:
        if con.in_transaction: con.rollback()
        con.close()


def _postgres(source, check, add, row_limit):
    import psycopg
    parameters = _explicit_postgres_parameters(source.location)
    with psycopg.connect(**parameters, autocommit=True) as con:
        con.execute('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        try:
            con.execute("SET LOCAL search_path = pg_catalog")
            con.execute("SET LOCAL statement_timeout = '1000ms'")
            con.execute("SET LOCAL lock_timeout = '1000ms'")
            con.execute("SET LOCAL idle_in_transaction_session_timeout = '5000ms'")
            con.execute('SET LOCAL row_security = off')
            check()
            relations = {}
            for table, kind, rls, forced in con.execute('''
                SELECT c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity
                FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' ORDER BY c.relname LIMIT %s''', (row_limit+1,)):
                add('relation', (table, kind, rls, forced))
                relations[table] = (kind, rls, forced)
            columns = {}
            column_shapes = {}
            for table, column, datatype, type_schema, nullable, modifier, generated, identity_ in con.execute('''
                SELECT c.relname,a.attname,t.typname,tn.nspname,a.attnotnull,a.atttypmod,a.attgenerated,a.attidentity
                FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                JOIN pg_catalog.pg_type t ON t.oid=a.atttypid
                JOIN pg_catalog.pg_namespace tn ON tn.oid=t.typnamespace
                WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped
                ORDER BY c.relname,a.attnum LIMIT %s''', (row_limit+1,)):
                add('column', (table, column, datatype, type_schema, nullable, modifier, generated, identity_))
                columns.setdefault(table, []).append((column, datatype, nullable))
                column_shapes.setdefault(table, []).append((type_schema, modifier, generated, identity_))
            keys = {}
            for table, column, ordinal in con.execute('''
                SELECT c.relname,a.attname,k.ordinality
                FROM pg_catalog.pg_constraint p JOIN pg_catalog.pg_class c ON c.oid=p.conrelid
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(attnum,ordinality)
                JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum
                WHERE n.nspname='public' AND p.contype='p'
                ORDER BY c.relname,k.ordinality LIMIT %s''', (row_limit+1,)):
                add('primary_key', (table, column, ordinal))
                keys.setdefault(table, []).append(column)
            migrations = ()
            lineage = 'UNVERIFIED'
            if (relations.get('schema_migrations') == ('r', False, False)
                    and tuple(columns.get('schema_migrations', ())) == _POSTGRES['schema_migrations']
                    and tuple(keys.get('schema_migrations', ())) == ('version',)):
                # Lock the verified plain table so concurrent DDL cannot swap it
                # for a view before reading its bounded lineage claims.
                con.execute('LOCK TABLE public.schema_migrations IN ACCESS SHARE MODE')
                claims = []
                for version, name in con.execute('''SELECT version,
                    CASE WHEN octet_length(name)<=128 THEN name END
                    FROM public.schema_migrations ORDER BY version LIMIT 47'''):
                    if name is None: raise ValueError('migration cell budget')
                    add('migration_claim', (version, name))
                    claims.append((version, name))
                migrations = tuple(claims)
                if migrations == _MIGRATIONS: lineage = 'MATCHED_COMPLETE'
                elif migrations == _MIGRATIONS[:len(migrations)]: lineage = 'MATCHED_PREFIX'
                else: lineage = 'MISMATCHED'
            recognized = (lineage == 'MATCHED_COMPLETE' and all(
                relations.get(table) == ('r', False, False)
                and tuple(columns.get(table, ())) == expected
                and all(shape == ('pg_catalog', -1, '', '') for shape in column_shapes.get(table, ()))
                and tuple(keys.get(table, ())) == _PRIMARY_KEYS[table]
                for table, expected in _POSTGRES.items()))
            fields = tuple(table+'.'+column for table, column in (
                ('market_events', 'event_ts'), ('market_events', 'ingest_ts'),
                ('historical_levels', 'available_ts'))
                if any(c[0] == column for c in columns.get(table, ())))
            return ('GRID_POSTGRESQL_LATEST_STATE_V1' if recognized else 'UNRECOGNIZED',
                    lineage, migrations, fields)
        finally:
            con.execute('ROLLBACK')
