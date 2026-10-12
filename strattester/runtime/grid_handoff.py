"""Create an explicit handoff manifest for Bybit Cluster Grid after historical bootstrap."""
from __future__ import annotations
from pathlib import Path
import hashlib,json,time

def file_sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def verify_handoff(path):
    """Fail closed if a handoff is incomplete, modified, or missing its payload."""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("source") != "strattester":
        raise ValueError("unsupported handoff schema or source")
    if manifest.get("ready_for_grid_import") is not True:
        raise ValueError("handoff is not import-ready")
    science = manifest.get("science_bundle")
    if not isinstance(science, dict) or not science.get("path") or not science.get("sha256"):
        raise ValueError("missing science bundle fingerprint")
    for key in ("science_bundle", "strategy_results", "phase_manifest"):
        entry = manifest.get(key)
        if entry is None:
            continue
        if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
            raise ValueError(f"invalid {key} fingerprint")
        payload = Path(entry["path"])
        if not payload.is_file() or (key == "science_bundle" and not payload.stat().st_size):
            raise ValueError(f"missing or empty {key} payload")
        if file_sha256(payload) != entry["sha256"]:
            raise ValueError(f"{key} checksum mismatch")
    return manifest


def write_handoff(path,science_bundle_path,*,strategy_results_path=None,phase_manifest_path=None):
    science=Path(science_bundle_path)
    if not science.is_file():raise FileNotFoundError(science)
    if not science.stat().st_size:raise ValueError("science bundle is empty")
    out={
      "schema":1,
      "created_at":time.time(),
      "source":"strattester",
      "science_bundle":{"path":str(science),"sha256":file_sha256(science)},
      "strategy_results":None,
      "phase_manifest":None,
      "ready_for_grid_import":True,
    }
    if strategy_results_path:
        p=Path(strategy_results_path)
        if p.is_file():out["strategy_results"]={"path":str(p),"sha256":file_sha256(p)}
    if phase_manifest_path:
        p=Path(phase_manifest_path)
        if p.is_file():out["phase_manifest"]={"path":str(p),"sha256":file_sha256(p)}
    dest=Path(path)
    if dest.resolve()==science.resolve():
        raise ValueError("handoff destination must not overwrite science bundle")
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(dest.suffix+".tmp")
    tmp.write_text(json.dumps(out,sort_keys=True,indent=2),encoding="utf-8")
    tmp.replace(dest)
    return out
