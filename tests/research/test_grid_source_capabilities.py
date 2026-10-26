"""Physical catalog facts never grant historical export authority.

Fixtures are exact AST-extracted SQL from pinned Grid, not a history schema.
"""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sqlite3
import pytest

FIXTURE = Path(__file__).parents[1] / 'fixtures' / 'grid_native_ddl.json'


def ddl_fixture():
    return json.loads(FIXTURE.read_bytes())


def source(path, engine='sqlite'):
    from strattester.research.grid_source_capabilities import NativeGridSource
    return NativeGridSource('fixture', engine, str(path))


def inspect(item, **kwargs):
    from strattester.research.grid_source_capabilities import inspect_native_grid
    return inspect_native_grid(item, **kwargs)


def legacy(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute(ddl_fixture()['sqlite_legacy_test_ddl'])
        con.execute("INSERT INTO candles VALUES ('BTCUSDT',0,'1','2','0','1','10','11')")
    con.close()
    return path


def test_actual_legacy_catalog_is_recognized_without_promoting_history(tmp_path):
    path = legacy(tmp_path)
    before = path.read_bytes()
    report = inspect(source(path))
    assert report.adapter == 'GRID_LEGACY_CANDLES_SHAPE_V1'
    assert report.migration_lineage == 'NOT_APPLICABLE'
    assert report.status == 'BLOCKED' and report.eligible is False
    assert report.evidence_kind == 'READ_ONLY_CATALOG_OBSERVATION'
    assert report.source_commit == 'd537d525296ef34f727996e240ae6c60102c6082'
    assert report.coherence_epoch_id is None
    assert report.data_seal_sha256 is None
    assert report.missing_facts == (
        'first_availability_history', 'retained_revisions', 'cross_source_coherence',
        'market_partition_authority', 'source_completeness_receipts',
        'producer_issued_immutable_export', 'physical_schema_identity',
        'deployed_producer_identity',
    )
    assert len(report.catalog_sha256) == 64
    assert path.read_bytes() == before
    with pytest.raises(FrozenInstanceError):
        report.eligible = True


def test_schema_drift_is_unknown_and_never_exportable(tmp_path):
    path = legacy(tmp_path)
    with sqlite3.connect(path) as con:
        con.execute('ALTER TABLE candles ADD COLUMN first_available_ns INTEGER')
    report = inspect(source(path))
    assert report.adapter == 'UNRECOGNIZED'
    assert report.eligible is False and report.status == 'BLOCKED'
    assert 'unrecognized_catalog_shape' in report.missing_facts


def test_catalog_budget_and_cancellation_precede_io(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite3, 'connect', lambda *a, **k: pytest.fail('database accessed'))
    for options in ({'max_catalog_rows': 0}, {'max_catalog_rows': 2049}, {'max_bytes': 1048577}):
        with pytest.raises(ValueError, match='budget'):
            inspect(source(tmp_path/'missing.db'), **options)
    with pytest.raises(RuntimeError, match='cancelled'):
        inspect(source(tmp_path/'missing.db'), cancel=lambda: True)


def test_catalog_limit_rejects_large_catalog_and_large_cells(tmp_path):
    path = legacy(tmp_path)
    with pytest.raises(ValueError, match='catalog row budget'):
        inspect(source(path), max_catalog_rows=2)
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE "' + 'x'*300 + '" (value TEXT)')
    with pytest.raises(ValueError, match='catalog cell budget'):
        inspect(source(path))


def test_missing_source_is_not_created(tmp_path):
    path = tmp_path/'absent.db'
    with pytest.raises((OSError, sqlite3.OperationalError)):
        inspect(source(path))
    assert not path.exists()


def test_catalog_fingerprint_changes_on_ddl_but_not_market_values(tmp_path):
    path = legacy(tmp_path)
    first = inspect(source(path))
    with sqlite3.connect(path) as con:
        con.execute("UPDATE candles SET close='999'")
    assert inspect(source(path)).catalog_sha256 == first.catalog_sha256
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE extra (value TEXT)')
    assert inspect(source(path)).catalog_sha256 != first.catalog_sha256


def test_caller_history_claims_are_not_accepted(tmp_path):
    from strattester.research.grid_producer_readiness import require_native_grid_export
    with pytest.raises(TypeError):
        inspect(source(legacy(tmp_path)), first_availability_retained=True)
    with pytest.raises(RuntimeError, match='native Grid export BLOCKED'):
        require_native_grid_export()


@pytest.fixture
def native_postgres(tmp_path, monkeypatch):
    """Own only this new dataDir and ephemeral port; reuse reviewed ACL/stop helpers."""
    import os
    import socket
    import subprocess
    import sys
    import time
    from tests.research.test_financial_grid_exporter import (
        isolate_postgres_fixture_environment, owned_postgres_fixture_root,
        stop_owned_postgres,
    )
    explicit = isolate_postgres_fixture_environment(monkeypatch)
    psycopg = pytest.importorskip('psycopg')
    candidates = [Path(explicit)] if explicit else [
        *sorted(Path('C:/Program Files/PostgreSQL').glob('*/bin'), reverse=True),
        *sorted(Path('/usr/lib/postgresql').glob('*/bin'), reverse=True),
    ]
    suffix = '.exe' if os.name == 'nt' else ''
    binary = next((p for p in candidates if (p/('initdb'+suffix)).is_file()), None)
    if binary is None:
        if explicit or os.environ.get('CI'):
            pytest.fail('required PostgreSQL fixture binaries unavailable')
        pytest.skip('optional local PostgreSQL fixture binaries unavailable')
    root = owned_postgres_fixture_root(tmp_path)
    data = root/'pg-native-owned'
    initialized = subprocess.run([
        str(binary/('initdb'+suffix)), '-D', str(data), '-A', 'trust', '-U', 'fixture',
        '--no-locale', '--encoding=UTF8',
    ], capture_output=True, text=True, timeout=30)
    assert initialized.returncode == 0, initialized.stdout+initialized.stderr
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    assert port != 5432
    log = root/'pg-native-owned.log'
    process = None
    with log.open('wb') as stream:
        try:
            if os.name == 'nt':
                stream.close()
                with (root/'pg-native-control.log').open('wb') as control:
                    started = subprocess.run([
                        str(binary/'pg_ctl.exe'), '-D', str(data), '-l', str(log),
                        '-o', f'-p {port} -h 127.0.0.1 -c max_connections=8 -c unix_socket_directories=',
                        '-w', '-t', '20', 'start',
                    ], stdout=control, stderr=subprocess.STDOUT, timeout=30)
                assert started.returncode == 0, log.read_text()
            else:
                process = subprocess.Popen([
                    str(binary/'postgres'), '-D', str(data), '-p', str(port), '-h', '127.0.0.1',
                    '-c', 'max_connections=8', '-c', 'unix_socket_directories=',
                ], stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
            dsn = f'host=127.0.0.1 port={port} dbname=postgres user=fixture connect_timeout=1'
            for _ in range(100):
                try:
                    with psycopg.connect(dsn): pass
                    break
                except psycopg.OperationalError:
                    time.sleep(.05)
            else: pytest.fail('owned PostgreSQL fixture startup timeout')
            fixture = ddl_fixture()
            with psycopg.connect(dsn) as con:
                con.execute(fixture['postgres_base'])
                for version, name, statements in fixture['migrations']:
                    for statement in statements: con.execute(statement)
                    con.execute('INSERT INTO schema_migrations(version,name) VALUES (%s,%s)', (version, name))
            yield dsn, psycopg
        finally:
            stop_owned_postgres(binary, data, suffix, process, primary_error=sys.exception())


def test_actual_postgres_ddl_has_ingestion_but_no_candle_history(native_postgres):
    dsn, _ = native_postgres
    report = inspect(source(dsn, 'postgresql'))
    assert report.adapter == 'GRID_POSTGRESQL_LATEST_STATE_V1'
    assert report.migration_lineage == 'MATCHED_COMPLETE'
    assert report.migrations[-1] == (46, 'scientific_method_event_idempotency')
    assert report.observed_fields == (
        'market_events.event_ts', 'market_events.ingest_ts', 'historical_levels.available_ts',
    )
    assert report.status == 'BLOCKED' and not report.eligible
    assert report.coherence_epoch_id is None and report.data_seal_sha256 is None
    assert 'retained_revisions' in report.missing_facts


@pytest.mark.parametrize('mutation', [
    "UPDATE schema_migrations SET name='forged' WHERE version=8",
    'DELETE FROM schema_migrations WHERE version=8',
    "INSERT INTO schema_migrations(version,name) VALUES (47,'unreviewed')",
    'ALTER TABLE candles_1m DROP CONSTRAINT candles_1m_pkey',
    'ALTER TABLE candles_1m ADD COLUMN first_available_ns bigint',
])
def test_postgres_drift_never_reuses_native_adapter(native_postgres, mutation):
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn) as con: con.execute(mutation)
    report = inspect(source(dsn, 'postgresql'))
    assert report.adapter == 'UNRECOGNIZED'
    assert report.status == 'BLOCKED' and not report.eligible


def test_postgres_catalog_reader_handles_view_as_untrusted_lineage(native_postgres):
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn) as con:
        con.execute('ALTER TABLE schema_migrations RENAME TO migrations_hidden')
        con.execute("CREATE VIEW schema_migrations AS SELECT 1::bigint AS version, 'fake'::text AS name, now() AS applied_at")
    report = inspect(source(dsn, 'postgresql'))
    assert report.migration_lineage == 'UNVERIFIED'
    assert report.adapter == 'UNRECOGNIZED'


def test_postgres_catalog_bounds_untrusted_migration_cells(native_postgres):
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn) as con:
        con.execute("UPDATE schema_migrations SET name=repeat('x',1000000) WHERE version=8")
    with pytest.raises(ValueError, match='migration cell budget'):
        inspect(source(dsn, 'postgresql'))


@pytest.mark.parametrize('statement', [
    'ALTER TABLE candles_1m ALTER COLUMN close TYPE numeric(12,2)',
    'ALTER TABLE candles_1m ENABLE ROW LEVEL SECURITY',
])
def test_postgres_adapter_rejects_precision_and_row_security_drift(native_postgres, statement):
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn) as con: con.execute(statement)
    assert inspect(source(dsn, 'postgresql')).adapter == 'UNRECOGNIZED'


def test_catalog_access_needs_no_permission_to_read_market_data(native_postgres):
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn) as con:
        con.execute('CREATE ROLE catalog_reader LOGIN')
        con.execute('GRANT SELECT ON schema_migrations TO catalog_reader')
    limited = dsn.replace('user=fixture', 'user=catalog_reader')
    with psycopg.connect(limited) as con:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            con.execute('SELECT * FROM candles_1m')
    report = inspect(source(limited, 'postgresql'))
    assert report.adapter == 'GRID_POSTGRESQL_LATEST_STATE_V1'
    assert not report.eligible


def test_same_named_user_type_cannot_impersonate_postgres_numeric(native_postgres):
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn) as con:
        con.execute('CREATE DOMAIN public.numeric AS pg_catalog.numeric')
        con.execute('ALTER TABLE candles_1m ALTER COLUMN close TYPE public.numeric')
    assert inspect(source(dsn, 'postgresql')).adapter == 'UNRECOGNIZED'


@pytest.mark.parametrize('phase', ['after_catalog', 'before_lock'])
def test_concurrent_lineage_view_replacement_cannot_execute_its_function(native_postgres, monkeypatch, phase):
    """A real second connection swaps the name after catalog inspection.

    The instrumentation only selects the interleaving; both connections and
    every catalog/DDL/lineage statement execute against the owned PostgreSQL.
    """
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn, autocommit=True) as writer:
        writer.execute('''CREATE FUNCTION public.catalog_view_tripwire() RETURNS text
            LANGUAGE plpgsql VOLATILE AS $$ BEGIN
            RAISE EXCEPTION 'UNTRUSTED_LINEAGE_VIEW_FUNCTION_EXECUTED'; END $$''')
        real_execute = psycopg.Connection.execute
        race = {'attempted': False, 'blocked': False, 'replacement_committed': False}

        def replace_name():
            race['attempted'] = True
            try:
                with writer.transaction():
                    writer.execute("SET LOCAL lock_timeout = '100ms'")
                    writer.execute('ALTER TABLE public.schema_migrations RENAME TO original_migrations')
                    writer.execute('''CREATE VIEW public.schema_migrations AS
                        SELECT 1::bigint AS version,
                        public.catalog_view_tripwire() AS name, now() AS applied_at''')
                race['replacement_committed'] = True
            except psycopg.errors.LockNotAvailable:
                race['blocked'] = True

        def execute(connection, query, *args, **kwargs):
            if (connection is not writer and not race['attempted'] and phase == 'before_lock'
                    and 'LOCK TABLE' in str(query) and 'public.schema_migrations' in str(query)):
                replace_name()
            cursor = real_execute(connection, query, *args, **kwargs)
            if (connection is not writer and not race['attempted'] and phase == 'after_catalog'
                    and 'FROM pg_catalog.pg_constraint p' in str(query)):
                replace_name()
            return cursor

        monkeypatch.setattr(psycopg.Connection, 'execute', execute)
        report = inspect(source(dsn, 'postgresql'))
        if phase == 'after_catalog':
            assert race == {'attempted': True, 'blocked': True, 'replacement_committed': False}
            assert report.migration_lineage == 'MATCHED_COMPLETE'
        else:
            assert race == {'attempted': True, 'blocked': False, 'replacement_committed': True}
            assert report.migration_lineage == 'UNVERIFIED'
            assert report.adapter == 'UNRECOGNIZED'
        assert report.status == 'BLOCKED' and report.eligible is False


def test_absent_lineage_table_remains_unverified_without_creating_it(native_postgres):
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn) as con:
        con.execute('DROP TABLE public.schema_migrations')
    report = inspect(source(dsn, 'postgresql'))
    assert report.migration_lineage == 'UNVERIFIED'
    assert report.adapter == 'UNRECOGNIZED'
    assert report.migrations == () and not report.eligible
    with psycopg.connect(dsn) as con:
        assert con.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None


def test_namespace_replacement_after_oid_recheck_never_evaluates_view(native_postgres, monkeypatch):
    """A relation lock does not lock its namespace's name against replacement."""
    dsn, psycopg = native_postgres
    with psycopg.connect(dsn, autocommit=True) as writer:
        writer.execute('''CREATE FUNCTION public.namespace_view_tripwire() RETURNS text
            LANGUAGE plpgsql VOLATILE AS $$ BEGIN
            RAISE EXCEPTION 'UNTRUSTED_NAMESPACE_VIEW_FUNCTION_EXECUTED'; END $$''')
        real_execute = psycopg.Connection.execute
        replaced = False

        def execute(connection, query, *args, **kwargs):
            nonlocal replaced
            cursor = real_execute(connection, query, *args, **kwargs)
            if (connection is not writer and not replaced
                    and 'EXISTS (SELECT 1 FROM pg_catalog.pg_locks' in str(query)):
                with writer.transaction():
                    writer.execute("SET LOCAL lock_timeout = '100ms'")
                    writer.execute('ALTER SCHEMA public RENAME TO replaced_namespace')
                    writer.execute('CREATE SCHEMA public')
                    writer.execute('''CREATE VIEW public.schema_migrations AS
                        SELECT 1::bigint AS version,
                        replaced_namespace.namespace_view_tripwire() AS name, now() AS applied_at''')
                replaced = True
            return cursor

        monkeypatch.setattr(psycopg.Connection, 'execute', execute)
        with pytest.raises(psycopg.errors.FeatureNotSupported, match='TABLESAMPLE'):
            inspect(source(dsn, 'postgresql'))
        assert replaced
