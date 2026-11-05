"""Create an explicit handoff manifest for Bybit Cluster Grid after historical bootstrap."""
from __future__ import annotations
from pathlib import Path
import hashlib,json,time

def file_sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def write_handoff(path,science_bundle_path,*,strategy_results_path=None,phase_manifest_path=None):
    science=Path(science_bundle_path)
    if not science.exists():raise FileNotFoundError(science)
    from strattester.research.scientific_bootstrap import DATASETS
    bundle=json.loads(science.read_text(encoding='utf-8'))
    ready=(bundle.get('schema')==1 and bundle.get('status')=='READY' and
           bundle.get('research_scope')=='HISTORICAL_BOOTSTRAP_ONLY' and
           bundle.get('live_promotion_allowed') is False and
           bool(bundle.get('symbols')) and all(row.get('status')=='READY' for row in bundle['symbols']) and
           all(bundle.get('capabilities',{}).get(dataset) is True for dataset in DATASETS))
    out={
      "schema":1,
      "created_at":time.time(),
      "source":"strattester",
      "science_bundle":{"path":str(science),"sha256":file_sha256(science)},
      "strategy_results":None,
      "phase_manifest":None,
      "ready_for_grid_import":ready,
      "research_scope":"HISTORICAL_BOOTSTRAP_ONLY",
      "live_promotion_allowed":False,
    }
    if strategy_results_path:
        p=Path(strategy_results_path)
        if p.exists():out["strategy_results"]={"path":str(p),"sha256":file_sha256(p)}
    if phase_manifest_path:
        p=Path(phase_manifest_path)
        if p.exists():out["phase_manifest"]={"path":str(p),"sha256":file_sha256(p)}
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(dest.suffix+".tmp")
    tmp.write_text(json.dumps(out,sort_keys=True,indent=2),encoding="utf-8")
    tmp.replace(dest)
    return out
