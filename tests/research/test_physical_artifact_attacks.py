import hashlib
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from strattester.research.financial_snapshot import verified_bytes, load_snapshot
from strattester.research.financial_checkpoint import save_checkpoint
from strattester.research.financial_structural_model import StructuralConfig, build_structural_model


def test_hardlinked_artifact_is_not_admitted(tmp_path):
    original=tmp_path/'one';original.write_bytes(b'fixture')
    linked=tmp_path/'two';os.link(original,linked)
    with pytest.raises(ValueError,match='link|identity'):
        verified_bytes(linked,hashlib.sha256(b'fixture').hexdigest(),100)


def test_mutated_staging_file_never_returns_registered_digest(tmp_path):
    target=tmp_path/'model.json';real_link=os.link
    def mutate(source,destination):
        Path(source).write_bytes(b'{"mutated":true}')
        return real_link(source,destination)
    with patch('strattester.research.financial_checkpoint.os.link',mutate):
        with pytest.raises(ValueError):
            save_checkpoint(build_structural_model(StructuralConfig()),target,dataset_sha256='a'*64,seed=0)
    assert target.exists()  # unregistered failed publication; preserve evidence
    assert not list(tmp_path.glob('.checkpoint-*'))


@pytest.mark.parametrize('data',[b'['*1200+b'0'+b']'*1200,b'[]',b'{"version":NaN}'],ids=['deep','array','nonfinite'])
def test_malformed_snapshot_is_bounded_contract_error(tmp_path,data):
    path=tmp_path/'bad.json';path.write_bytes(data)
    with pytest.raises(ValueError):
        load_snapshot(path,hashlib.sha256(data).hexdigest(),trusted_producers=set(),expected_coherence='x')


def test_failed_publication_never_unlinks_a_raced_replacement(tmp_path):
    target=tmp_path/'model.json';replacement=tmp_path/'known-good.json'
    replacement.write_bytes(b'known-good');real_link=os.link;real_unlink=Path.unlink
    def mutate(source,destination):
        Path(source).write_bytes(b'bad stage');return real_link(source,destination)
    def race_unlink(path,*args,**kwargs):
        if path==target:os.replace(replacement,target)
        return real_unlink(path,*args,**kwargs)
    with patch('strattester.research.financial_checkpoint.os.link',mutate), patch.object(Path,'unlink',race_unlink):
        with pytest.raises(ValueError):
            save_checkpoint(build_structural_model(StructuralConfig()),target,dataset_sha256='a'*64,seed=0)
    # No target-path unlink is permitted on failure, even after an identity check.
    assert replacement.exists()
    assert target.exists()
