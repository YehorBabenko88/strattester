import sqlite3

import pytest

from strattester.marketdata.sqlite_store import SQLiteMarketStore


@pytest.mark.parametrize('version', ['3', '999', '', 'invalid', '2.5', '-1', '0', None])
def test_open_rejects_unsupported_schema_without_changing_database(tmp_path, version):
    path = tmp_path / 'market.db'
    # DELETE mode makes a premature switch to WAL observable in the source bytes.
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT)')
        connection.execute('INSERT INTO schema_meta VALUES (?, ?)', ('schema_version', version))
        connection.execute('CREATE TABLE future_payload (data TEXT)')
        connection.execute("INSERT INTO future_payload VALUES ('preserve me')")
    connection.close()
    before = path.read_bytes()

    with pytest.raises(sqlite3.DatabaseError, match='schema version'):
        SQLiteMarketStore.open(path)

    assert path.read_bytes() == before
    assert not path.with_name(path.name + '-wal').exists()
    assert not path.with_name(path.name + '-shm').exists()


@pytest.mark.parametrize('version', ['1', '2', None])
def test_open_bootstraps_known_versions_and_missing_version_metadata(tmp_path, version):
    path = tmp_path / 'market.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        if version is not None:
            connection.execute('INSERT INTO schema_meta VALUES (?, ?)', ('schema_version', version))
    connection.close()

    store = SQLiteMarketStore.open(path)
    try:
        assert store.connection.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone() == ('2',)
        assert store.coverage('BTCUSDT', 'candles', '1m', 60000).count == 0
    finally:
        store.close()


def test_open_rejects_future_version_in_existing_market_store(tmp_path):
    path = tmp_path / 'market.db'
    store = SQLiteMarketStore.open(path)
    store.connection.execute("UPDATE schema_meta SET value='999' WHERE key='schema_version'")
    store.connection.commit()
    store.close()
    before = path.read_bytes()

    with pytest.raises(sqlite3.DatabaseError, match='schema version'):
        SQLiteMarketStore.open(path)

    assert path.read_bytes() == before
