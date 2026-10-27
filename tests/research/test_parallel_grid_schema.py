"""Independent disposable SQLite schema-membership regression fixtures."""
from contextlib import closing
from dataclasses import asdict
import sqlite3

import pytest

from strattester.research.financial_contract import Bar, Instrument
from strattester.research.financial_grid_exporter import (
    DDL, PROFILE, SCHEMA_SHA256, HistoryProfile, HistorySource,
    export_history, history_seal,
)
from strattester.research.financial_signed_export import MarketPartition
from strattester.research.financial_snapshot import canonical_bytes


def sealed_source(tmp_path, extra_sql=None, engine='sqlite'):
    path = tmp_path / 'owned.db'
    partition = MarketPartition('bybit', 'linear', 'BTCUSDT', 10)
    bar = Bar(Instrument('bybit', 'linear', 'BTCUSDT'), 10, 0, 10, 9,
              10, 10, 30, 100., 'VERIFIED', True, True, 1, 'producer', 'a'*40)
    rows = [dict(bar=asdict(bar), first_available_ns=10,
                 source_id='source', coherence_epoch_id='epoch')]
    meta = dict(source_id='source', snapshot_id='cut', coherence_epoch_id='epoch',
                schema_sha256=SCHEMA_SHA256, complete=True,
                first_availability_retained=True, revision_history_retained=True,
                event_watermark_ns=30, availability_watermark_ns=30,
                partitions=[asdict(partition)])
    with closing(sqlite3.connect(path)) as connection, connection:
        for statement in DDL:
            connection.execute(statement)
        connection.execute('INSERT INTO history_meta VALUES (?)', (canonical_bytes(meta).decode(),))
        connection.execute('INSERT INTO history_rows VALUES (?)', (canonical_bytes(rows[0]).decode(),))
        if extra_sql:
            connection.execute(extra_sql)
    source = HistorySource('source', engine, str(path), 'cut', history_seal(meta, rows), (partition,))
    return HistoryProfile(PROFILE, 'epoch', 30, (source,))


def publish(profile, destination):
    return export_history(profile, destination, producer_id='producer',
                          producer_build_sha='a'*40, key_id='key',
                          export_id='export', issued_at_ns=31)


@pytest.mark.parametrize('engine', ['sqlite', 'sharded_sqlite'])
@pytest.mark.parametrize('extra_sql', [
    'CREATE VIEW unexpected AS SELECT payload FROM history_rows',
    'CREATE INDEX unexpected ON history_rows(payload)',
    'CREATE TRIGGER unexpected AFTER INSERT ON history_rows BEGIN SELECT 1; END',
])
def test_unsealed_schema_membership_is_rejected_before_publication(tmp_path, engine, extra_sql):
    profile = sealed_source(tmp_path, extra_sql, engine)
    destination = tmp_path / 'output'
    with pytest.raises(ValueError, match='physical schema identity'):
        publish(profile, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob('.history-export-*'))


@pytest.mark.parametrize('engine', ['sqlite', 'sharded_sqlite'])
def test_exact_schema_still_exports(tmp_path, engine):
    result = publish(sealed_source(tmp_path, engine=engine), tmp_path / 'output')
    assert len(result.snapshot.bars) == 1
    assert result.directory.is_dir()
