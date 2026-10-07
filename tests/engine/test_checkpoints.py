import pytest
from strattester.engine.checkpoints import Checkpoint,encode_checkpoint,decode_checkpoint,require_compatible_checkpoint

def test_checkpoint_roundtrip_and_compatibility():
    cp=Checkpoint('job-1','cfg','fp','cursor-10')
    raw=encode_checkpoint(cp)
    assert decode_checkpoint(raw)==cp
    assert require_compatible_checkpoint(raw,'job-1','cfg','fp')==cp

def test_checkpoint_rejects_changed_strategy_or_config():
    raw=encode_checkpoint(Checkpoint('job-1','cfg-v1','fp-v1','cursor'))
    with pytest.raises(RuntimeError):
        require_compatible_checkpoint(raw,'job-1','cfg-v2','fp-v1')
    with pytest.raises(RuntimeError):
        require_compatible_checkpoint(raw,'job-1','cfg-v1','fp-v2')

def test_checkpoint_rejects_different_job():
    raw=encode_checkpoint(Checkpoint('job-1','cfg','fp','cursor'))
    with pytest.raises(RuntimeError):
        require_compatible_checkpoint(raw,'job-2','cfg','fp')
