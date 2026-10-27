import pytest
from dataclasses import replace
from strattester.alphafold_snapshot_contract import (
    SourceSnapshot, SnapshotContractError, validate_snapshot_manifest,
)


def sample(source_id):
    return SourceSnapshot(source_id, "snapshot-1", "v1", 120, 130, "a" * 64)


def validate(sources):
    return validate_snapshot_manifest(
        tuple(sources), required_source_ids=frozenset({"sqlite-1", "pg-1"}),
        expected_schema_version="v1", event_cutoff=100, knowledge_cutoff=130,
    )


def test_complete_manifest():
    validate([sample("sqlite-1"), sample("pg-1")])


@pytest.mark.parametrize("sources", [
    [sample("sqlite-1")],
    [sample("sqlite-1"), sample("sqlite-1")],
    [sample("sqlite-1"), sample("unexpected")],
    [sample("sqlite-1"), replace(sample("pg-1"), event_watermark=99)],
    [sample("sqlite-1"), replace(sample("pg-1"), knowledge_cutoff=131)],
    [sample("sqlite-1"), replace(sample("pg-1"), schema_version="v2")],
    [sample("sqlite-1"), replace(sample("pg-1"), dataset_sha256="invalid")],
])
def test_inconsistent_manifest_rejected(sources):
    with pytest.raises(SnapshotContractError):
        validate(sources)
