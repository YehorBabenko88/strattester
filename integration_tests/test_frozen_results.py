from contextlib import closing
from hashlib import sha256
import sqlite3

import pytest
from terminan.paper_ledger import PaperReplayLedger
from terminan.research_archive import ResearchArchive

from strattester.persistence.frozen_results import import_frozen_results


LEGACY_FIELDS = (
    "run_id TEXT NOT NULL, symbol TEXT NOT NULL, strategy_id TEXT NOT NULL, "
    "strategy_version TEXT NOT NULL, created_at REAL NOT NULL, metrics TEXT NOT NULL"
)
LEGACY_KEY = ", PRIMARY KEY(run_id, symbol, strategy_id, strategy_version)"


def make_backup(path):
    row = ("run", "BTCUSDT", "legacy", "1", 123.125, '{"fold":2,"score":NaN}')
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            f"CREATE TABLE research_results({LEGACY_FIELDS}{LEGACY_KEY})"
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
    assert set(receipt["tables"]) == {"research_results"}
    assert receipt["source_snapshot_sha256"] == digest
    assert import_frozen_results(source, digest, "legacy", ledger) == receipt
    restored = ResearchArchive(PaperReplayLedger(ledger))
    assert list(restored.read_snapshot("legacy")) == [
        ("research_results", "LEGACY_UNFENCED", row),
    ]
    assert source.read_bytes() == before
    assert not list(tmp_path.glob("archive #1.sqlite-*"))

    restored_ledger = tmp_path / "restored.sqlite"
    with closing(sqlite3.connect(ledger)) as connection, closing(sqlite3.connect(restored_ledger)) as copy:
        connection.backup(copy)
    assert import_frozen_results(source, digest, "legacy", restored_ledger) == receipt


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


def test_legacy_with_present_empty_staged_table_is_not_treated_as_absent(tmp_path):
    source = tmp_path / "ambiguous.sqlite"
    make_backup(source)
    with closing(sqlite3.connect(source)) as connection, connection:
        connection.execute(
            f"CREATE TABLE staged_research_results(stage_id TEXT PRIMARY KEY, {LEGACY_FIELDS}, "
            "job_id TEXT, lease_token INTEGER NOT NULL DEFAULT 0, "
            "node_generation INTEGER NOT NULL DEFAULT 0)"
        )
    raw = source.read_bytes()
    destination = tmp_path / "terminan.sqlite"
    with pytest.raises(ValueError, match="mixed legacy and staged result schema"):
        import_frozen_results(source, sha256(raw).hexdigest(), "ambiguous", destination)
    assert source.read_bytes() == raw
    assert not destination.exists()


@pytest.mark.parametrize("timestamps", [(), (float("inf"), -0.0, float("-inf"))])
def test_native_legacy_receipt_preserves_zero_and_infinite_rows(tmp_path, timestamps):
    source = tmp_path / "old.sqlite"
    make_backup(source)
    with closing(sqlite3.connect(source)) as connection, connection:
        connection.execute("DELETE FROM research_results")
        connection.executemany(
            "INSERT INTO research_results VALUES (?,?,?,?,?,?)",
            [(f"run-{index}", "BTCUSDT", "legacy", "1", timestamp, '{"value": Infinity}')
             for index, timestamp in reversed(list(enumerate(timestamps)))],
        )
        expected = connection.execute(
            "SELECT * FROM research_results ORDER BY run_id"
        ).fetchall()
    original = source.read_bytes()
    ledger = tmp_path / "terminan.sqlite"
    receipt = import_frozen_results(source, sha256(original).hexdigest(), "legacy", ledger)
    assert receipt["tables"]["research_results"]["row_count"] == len(expected)
    actual = [row for _, _, row in ResearchArchive(PaperReplayLedger(ledger)).read_snapshot("legacy")]
    assert actual == expected
    assert [row[4].hex() for row in actual] == [row[4].hex() for row in expected]
    assert source.read_bytes() == original


@pytest.mark.parametrize("definition", [
    LEGACY_FIELDS,
    LEGACY_FIELDS + ", PRIMARY KEY(symbol, run_id, strategy_id, strategy_version)",
    LEGACY_FIELDS.replace("created_at REAL", "created_at NUMERIC") + LEGACY_KEY,
    LEGACY_FIELDS.replace("run_id TEXT NOT NULL", "run_id TEXT") + LEGACY_KEY,
    LEGACY_FIELDS.replace("metrics TEXT NOT NULL", "metrics TEXT") + LEGACY_KEY,
    LEGACY_FIELDS + ", hidden_copy TEXT GENERATED ALWAYS AS (metrics) VIRTUAL" + LEGACY_KEY,
])
def test_noncanonical_legacy_schema_refused_without_destination(tmp_path, definition):
    source = tmp_path / "old.sqlite"
    with closing(sqlite3.connect(source)) as connection, connection:
        connection.execute(f"CREATE TABLE research_results({definition})")
    original = source.read_bytes()
    ledger = tmp_path / "terminan.sqlite"
    with pytest.raises(ValueError, match="unrecognized published result schema"):
        import_frozen_results(source, sha256(original).hexdigest(), "invalid", ledger)
    assert source.read_bytes() == original
    assert not ledger.exists()
    assert list(tmp_path.iterdir()) == [source]


def test_modern_published_schema_refuses_malformed_staging(tmp_path):
    from strattester.persistence.result_store import ResultStore

    source = tmp_path / "current.sqlite"
    store = ResultStore.open(source)
    with closing(store.con), store.con:
        store.con.execute("DROP TABLE staged_research_results")
        store.con.execute(
            f"CREATE TABLE staged_research_results(stage_id TEXT, {LEGACY_FIELDS}, "
            "job_id TEXT, lease_token INTEGER NOT NULL DEFAULT 0, "
            "node_generation INTEGER NOT NULL DEFAULT 0)"
        )
    original = source.read_bytes()
    ledger = tmp_path / "terminan.sqlite"
    with pytest.raises(ValueError, match="unrecognized or missing staged result schema"):
        import_frozen_results(source, sha256(original).hexdigest(), "invalid", ledger)
    assert source.read_bytes() == original
    assert not ledger.exists()


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
