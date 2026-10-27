"""Independent fail-closed checks: source inspection never grants export permission."""
from dataclasses import FrozenInstanceError
import pytest
from strattester.research.grid_producer_readiness import (
    GRID_SOURCE_COMMIT, NativeGridExportBlocked, pinned_grid_readiness,
    require_native_grid_export, verify_pinned_grid_source,
)


def test_source_inspection_is_explicitly_blocked_and_immutable():
    report = pinned_grid_readiness()
    assert report.status == 'BLOCKED'
    assert report.eligible is False
    assert report.evidence_kind == 'PINNED_SOURCE_INSPECTION'
    assert report.source_commit == GRID_SOURCE_COMMIT
    assert len(report.source_receipts) == 8
    assert {'first_availability_history', 'retained_revisions',
            'cross_source_coherence', 'market_partition_authority',
            'physical_schema_identity'} <= set(report.missing_facts)
    with pytest.raises(FrozenInstanceError):
        report.eligible = True


def test_native_export_never_returns_snapshot_even_with_truthy_claims():
    with pytest.raises(NativeGridExportBlocked, match='first_availability_history'):
        require_native_grid_export()
    with pytest.raises(TypeError):
        require_native_grid_export(eligible=True, revision_history=True)


@pytest.mark.parametrize('commit', ['', 'a'*40, GRID_SOURCE_COMMIT.upper(), None])
def test_wrong_commit_cannot_reuse_source_assessment(commit):
    with pytest.raises(ValueError, match='commit'):
        verify_pinned_grid_source(commit, {})


@pytest.mark.parametrize('files', [{}, {'../../database.sqlite': b'x'},
                                   {'grid/db.py': b'forged'}])
def test_missing_extra_and_forged_sources_fail_closed(files):
    with pytest.raises(ValueError, match='source membership'):
        verify_pinned_grid_source(GRID_SOURCE_COMMIT, files)


def test_digest_claims_are_not_source_bytes():
    files = {r.path: r.sha256 for r in pinned_grid_readiness().source_receipts}
    with pytest.raises(ValueError, match='source bytes'):
        verify_pinned_grid_source(GRID_SOURCE_COMMIT, files)


def test_tampering_with_exact_membership_still_fails():
    files = {r.path: b'changed' for r in pinned_grid_readiness().source_receipts}
    with pytest.raises(ValueError, match='source digest'):
        verify_pinned_grid_source(GRID_SOURCE_COMMIT, files)
