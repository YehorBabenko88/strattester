import pytest
from strattester.grid_bridge import digest,make_manifest,validate_manifest


def test_grid_handoff_is_deterministic():
    cfg={"z":2,"a":1}; spec={"symbol":"BTCUSDT","strategy":"smc"}
    m=make_manifest(run_id="r",job_id="j",job_type="backtest",dataset_hash="dataset",
      code_version="commit",config=cfg,input_spec=spec,result={"trades":10},metrics={"pnl":1.2})
    assert m["config_hash"]==digest({"a":1,"z":2})
    assert validate_manifest(m,{"dataset_hash":"dataset","code_version":"commit",
      "config_hash":digest(cfg),"input_hash":digest(spec)})
    bad=dict(m); bad["result"]={"trades":11}
    with pytest.raises(ValueError,match="result hash"):
        validate_manifest(bad)


def test_grid_handoff_fences_wrong_job():
    m=make_manifest(run_id="r",job_id="j",job_type="train",dataset_hash="d",
      code_version="c",config={},input_spec={})
    with pytest.raises(ValueError,match="job_id mismatch"):
        validate_manifest(m,{"job_id":"other"})
