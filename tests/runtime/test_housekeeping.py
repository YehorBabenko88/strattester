from pathlib import Path
from strattester.runtime.housekeeping import cleanup_artifacts

def _old(path,now=1000):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'abc')
    import os;os.utime(path,(now-100,now-100));return path

def test_cleanup_only_allowlisted_stale_files(tmp_path):
    old=_old(tmp_path/'a.tmp');keep=_old(tmp_path/'market.db');fresh=tmp_path/'fresh.part';fresh.write_bytes(b'x')
    report=cleanup_artifacts(tmp_path,older_than_seconds=50,now=1000)
    assert not old.exists() and keep.exists() and fresh.exists()
    assert report.reclaimed_bytes==3

def test_cleanup_never_deletes_active_path(tmp_path):
    active=_old(tmp_path/'work.stage')
    report=cleanup_artifacts(tmp_path,older_than_seconds=1,active_paths=[active],now=1000)
    assert active.exists() and str(active.resolve()) in report.skipped_active

def test_cleanup_is_bounded(tmp_path):
    for i in range(5):_old(tmp_path/f'{i}.tmp')
    report=cleanup_artifacts(tmp_path,older_than_seconds=1,limit=2,now=1000)
    assert len(report.deleted)==2
    assert len(list(tmp_path.glob('*.tmp')))==3

def test_cleanup_does_not_follow_symlink_outside_root(tmp_path):
    outside=tmp_path.parent/'outside-cleanup-target.tmp';outside.write_bytes(b'never delete')
    link=tmp_path/'link.tmp'
    try:link.symlink_to(outside)
    except (OSError,NotImplementedError):return
    cleanup_artifacts(tmp_path,older_than_seconds=0,now=1000)
    assert outside.exists()
    link.unlink(missing_ok=True);outside.unlink(missing_ok=True)

def test_cleanup_preserves_database_wal_logs_and_current_checkpoint(tmp_path):
    for name in ('market.db','market.db-wal','runtime.log','brain.checkpoint'):
        _old(tmp_path/name)
    cleanup_artifacts(tmp_path,older_than_seconds=1,now=1000)
    assert all((tmp_path/name).exists() for name in ('market.db','market.db-wal','runtime.log','brain.checkpoint'))
