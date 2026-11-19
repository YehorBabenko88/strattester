"""Import a verified frozen Strattester result backup into Terminan."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from strattester.marketdata.integrity import connect_read_only


_LEGACY = ("run_id", "symbol", "strategy_id", "strategy_version", "created_at", "metrics")
_PUBLISHED = (*_LEGACY, "job_id", "lease_token", "node_generation")
_STAGED = ("stage_id", *_PUBLISHED)
_MAX_BACKUP_BYTES = 4 * 1024**3
_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _verify_no_sidecars(source):
    if any(Path(f"{source}{suffix}").exists() for suffix in _SIDECAR_SUFFIXES):
        raise ValueError("use a standalone frozen SQLite backup without sidecars")


def _copy_verified(source, private_copy, expected_sha256):
    _verify_no_sidecars(source)
    digest = sha256()
    size = 0
    with source.open("rb") as origin, private_copy.open("xb") as destination:
        while chunk := origin.read(1024 * 1024):
            size += len(chunk)
            if size > _MAX_BACKUP_BYTES:
                raise ValueError("frozen SQLite backup exceeds size limit")
            digest.update(chunk)
            destination.write(chunk)
    _verify_no_sidecars(source)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("source snapshot SHA-256 mismatch")


def _columns(connection, table):
    # Only inspect real tables, never views that could synthesize rows.
    found = connection.execute(
        "SELECT type FROM sqlite_schema WHERE name=?", (table,)
    ).fetchone()
    if found is None:
        return ()
    if found != ("table",):
        raise ValueError("expected Strattester result table")
    return tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))


def import_frozen_results(source, expected_sha256, source_id, ledger_path):
    """Archive six- or nine-column results without opening the original in SQLite."""
    from terminan.paper_ledger import PaperReplayLedger
    from terminan.research_archive import ResearchArchive, research_result_receipt

    source, ledger_path = Path(source).resolve(strict=True), Path(ledger_path).resolve()
    if not source.is_file():
        raise ValueError("source must be a frozen SQLite backup file")
    source_files = {source, *(Path(f"{source}{suffix}") for suffix in _SIDECAR_SUFFIXES)}
    ledger_files = {ledger_path, *(Path(f"{ledger_path}{suffix}") for suffix in _SIDECAR_SUFFIXES)}
    if source_files & ledger_files or any(source.samefile(path) for path in ledger_files if path.exists()):
        raise ValueError("source backup and Terminan ledger must be different files")
    with TemporaryDirectory(prefix="strattester-results-") as directory:
        private_copy = Path(directory) / "frozen.sqlite"
        _copy_verified(source, private_copy, expected_sha256)
        with closing(connect_read_only(private_copy)) as connection:
            published_columns = _columns(connection, "research_results")
            staged_columns = _columns(connection, "staged_research_results")
            if published_columns not in (_LEGACY, _PUBLISHED):
                raise ValueError("unrecognized published result schema")
            legacy = published_columns == _LEGACY
            if legacy and staged_columns:
                raise ValueError("mixed legacy and staged result schema")
            if not legacy and staged_columns != _STAGED:
                raise ValueError("unrecognized or missing staged result schema")

            projection = ", ".join(published_columns)

            def tables():
                published = connection.execute(
                    f"SELECT {projection} FROM research_results "
                    "ORDER BY run_id COLLATE BINARY, symbol COLLATE BINARY, "
                    "strategy_id COLLATE BINARY, strategy_version COLLATE BINARY"
                )
                if legacy:
                    return {"research_results": published}
                staged = connection.execute(
                    f"SELECT {', '.join(_STAGED)} FROM staged_research_results "
                    "ORDER BY stage_id COLLATE BINARY"
                )
                return {"research_results": published, "staged_research_results": staged}

            receipt = research_result_receipt(expected_sha256, tables())
            return ResearchArchive(PaperReplayLedger(ledger_path)).import_snapshot(
                source_id, tables(), receipt
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("source_sha256")
    parser.add_argument("source_id")
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    receipt = import_frozen_results(args.source, args.source_sha256, args.source_id, args.ledger)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
