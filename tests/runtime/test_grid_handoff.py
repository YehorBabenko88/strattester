from pathlib import Path
from strattester.runtime.grid_handoff import write_handoff

def test_handoff_requires_science_bundle(tmp_path):
    science=tmp_path/"science.json";science.write_text('{"x":1}',encoding="utf-8")
    out=write_handoff(tmp_path/"handoff.json",science)
    assert out["ready_for_grid_import"] is False
    assert out["science_bundle"]["sha256"]
    assert (tmp_path/"handoff.json").exists()


def test_partial_science_never_marks_handoff_ready(tmp_path):
    import json
    science=tmp_path/'science.json'
    science.write_text(json.dumps({'schema':1,'status':'PARTIAL','symbols':[{'status':'PARTIAL'}],
                                  'research_scope':'HISTORICAL_BOOTSTRAP_ONLY','live_promotion_allowed':False}))
    assert write_handoff(tmp_path/'handoff.json',science)['ready_for_grid_import'] is False
