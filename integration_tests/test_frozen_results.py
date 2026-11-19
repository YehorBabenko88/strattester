from contextlib import closing
from hashlib import sha256
import sqlite3

import pytest
from terminan.paper_ledger import PaperReplayLedger
from terminan.research_archive import ResearchArchive

from strattester.persistence.frozen_results import import_frozen_results


def make_backup(path):
    row = ("run", "BTCUSDT", "legacy", "1", 123.125, '{"fold":2,"score":NaN}')
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE research_results(run_id TEXT, symbol TEXT, strategy_id TEXT, "
            "strategy_version TEXT, created_at REAL, metrics TEXT)"
        )
        connection.execute("INSERT INTO research_results VALUES (?,?,?,?,?,?)", row)
    return row


def test_six_fields_preserved_on_import_retry_and_reopen(tmp_path):
    source = tmp_path / "archive #1.sqlite"
    row = make_backup(source)
    before = source.read_bytes()
    digest = sha256(before).hexdigest()
    ledger = tmp_path / "terminan.sqlite"
    receipt = import_frozen_results(source, digest, "legacy", ledger)
    assert receipt["tables"]["research_results"]["row_count"] == 1
    assert receipt["tables"]["staged_research_results"]["row_count"] == 0
    assert receipt["source_snapshot_sha256"] == digest
    assert import_frozen_results(source, digest, "legacy", ledger) == receipt
    restored = ResearchArchive(PaperReplayLedger(ledger))
    assert list(restored.read_snapshot("legacy")) == [
        ("research_results", "LEGACY_UNFENCED", (*row, None, 0, 0)),
    ]
    assert source.read_bytes() == before
    assert not list(tmp_path.glob("archive #1.sqlite-*"))


def test_wrong_hash_and_source_alias_fail_before_destination_write(tmp_path):
    source = tmp_path / "old.sqlite"
    make_backup(source)
    before = source.read_bytes()
    ledger = tmp_path / "terminan.sqlite"
    with pytest.raises(ValueError, match="snapshot SHA-256 mismatch"):
        import_frozen_results(source, "0" * 64, "legacy", ledger)
    with pytest.raises(ValueError, match="must be different"):
        import_frozen_results(source, sha256(before).hexdigest(), "legacy", source)
    with pytest.raises(ValueError, match="must be different"):
        import_frozen_results(source, sha256(before).hexdigest(), "legacy",
                              tmp_path / "old.sqlite-wal")
    assert source.read_bytes() == before
    assert not ledger.exists()


def test_current_schema_preserves_staged_results_as_unverified(tmp_path):
    from strattester.persistence.result_store import ResultStore

    live_fixture = tmp_path / "fixture.sqlite"
    source = tmp_path / "snapshot.sqlite"
    ledger = tmp_path / "terminan.sqlite"
    store = ResultStore.open(live_fixture)
    with closing(store.con), closing(sqlite3.connect(source)) as snapshot:
        store.stage("stage", "run", "BTCUSDT", "legacy", "1", {"variant": "BASE"},
                    created_at=123.125, job_id="job", lease_token=7, node_generation=3)
        expected = store.con.execute("SELECT * FROM staged_research_results").fetchone()
        store.con.backup(snapshot)
    before = source.read_bytes()
    receipt = import_frozen_results(source, sha256(before).hexdigest(), "current", ledger)
    assert receipt["tables"]["staged_research_results"]["row_count"] == 1
    archive = ResearchArchive(PaperReplayLedger(ledger))
    assert list(archive.read_snapshot("current")) == [
        ("staged_research_results", "STAGED_UNVERIFIED", expected),
    ]
    assert source.read_bytes() == before


def test_wal_database_refused_without_touching_sidecars(tmp_path):
    source = tmp_path / "old.sqlite"
    make_backup(source)
    ledger = tmp_path / "terminan.sqlite"
    with closing(sqlite3.connect(source)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE research_results SET created_at=999")
        writer.commit()
        paths = sorted(tmp_path.iterdir())
        before = [path.read_bytes() for path in paths]
        with pytest.raises(ValueError, match="frozen SQLite backup"):
            import_frozen_results(source, sha256(before[0]).hexdigest(), "legacy", ledger)
        assert sorted(tmp_path.iterdir()) == paths
        assert [path.read_bytes() for path in paths] == before
