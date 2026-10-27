import os
from hashlib import sha256
from pathlib import Path
import subprocess
import sqlite3
import pytest
from strattester.research.financial_snapshot import verified_bytes, read_sqlite_bars

@pytest.mark.skipif(os.name != 'nt', reason='actual Windows junction attack')
@pytest.mark.parametrize('reader', ['artifact', 'sqlite'])
def test_ancestor_windows_junction_is_rejected(tmp_path, reader):
    target=tmp_path/'target'; target.mkdir()
    artifact=target/'input'
    if reader == 'artifact':
        artifact.write_bytes(b'{}')
    else:
        with sqlite3.connect(artifact) as db:
            db.execute('CREATE TABLE research_bars (exchange,market_type,symbol,timeframe_ns,candle_open_ns,candle_close_ns,event_ns,ingest_ns,available_ns,watermark_ns,close,quality,eligible,complete,revision,producer,source_sha)')
    junction=tmp_path/'junction'
    result=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(target)],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(ValueError,match='reparse|symlink'):
            if reader == 'artifact':
                verified_bytes(junction/'input',sha256(b'{}').hexdigest(),100)
            else:
                tuple(read_sqlite_bars(junction/'input',origin_ns=120))
    finally:
        junction.rmdir()

@pytest.mark.skipif(os.name != 'nt', reason='actual Windows junction attack')
def test_checkpoint_publication_rejects_junction_parent(tmp_path):
    from strattester.research.financial_checkpoint import save_checkpoint
    from strattester.research.financial_structural_model import StructuralConfig, build_structural_model
    target=tmp_path/'target'; target.mkdir()
    junction=tmp_path/'junction'
    result=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(target)],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(ValueError,match='reparse|symlink'):
            save_checkpoint(build_structural_model(StructuralConfig()),junction/'model.json',dataset_sha256='a'*64,seed=0)
        assert not list(target.iterdir())
    finally:
        junction.rmdir()

@pytest.mark.parametrize('reader',['artifact','sqlite'])
def test_parent_traversal_is_rejected_before_normalization(tmp_path,reader):
    # Lexical contract test, not a claim about native POSIX traversal semantics.
    directory=tmp_path/'ordinary'; directory.mkdir()
    target=tmp_path/'input'
    if reader=='artifact':target.write_bytes(b'{}')
    else:
        with sqlite3.connect(target) as db:
            db.execute('CREATE TABLE research_bars (exchange,market_type,symbol,timeframe_ns,candle_open_ns,candle_close_ns,event_ns,ingest_ns,available_ns,watermark_ns,close,quality,eligible,complete,revision,producer,source_sha)')
    path=directory/'..'/'input'
    with pytest.raises(ValueError,match='parent traversal'):
        if reader=='artifact':verified_bytes(path,sha256(b'{}').hexdigest(),100)
        else:tuple(read_sqlite_bars(path,origin_ns=120))

def test_ordinary_relative_artifact_path_remains_accepted(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path('ordinary').mkdir()
    Path('ordinary/input').write_bytes(b'{}')
    assert verified_bytes(Path('ordinary/input'),sha256(b'{}').hexdigest(),100)==b'{}'
