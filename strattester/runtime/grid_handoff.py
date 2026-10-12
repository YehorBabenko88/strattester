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
    manifest_path = Path(path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("handoff manifest must be an object")
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
        if not payload.is_absolute():
            payload = manifest_path.parent / payload
        if payload.resolve() == manifest_path:
            raise ValueError(f"{key} payload points to handoff manifest")
        if not payload.is_file() or (key == "science_bundle" and not payload.stat().st_size):
            raise ValueError(f"missing or empty {key} payload")
        if file_sha256(payload) != entry["sha256"]:
            raise ValueError(f"{key} checksum mismatch")
    return manifest


def pack_handoff(source_manifest, destination_dir):
    """Copy verified handoff payloads into a portable directory atomically.

    Destination must be new; never replace an existing package or source files.
    """
    import shutil
    import uuid
    source_manifest = Path(source_manifest).resolve()
    data = verify_handoff(source_manifest)
    dest = Path(destination_dir).resolve()
    if dest.exists():
        raise FileExistsError(dest)
    if dest == source_manifest.parent or dest in source_manifest.parents:
        raise ValueError("package destination must not contain source manifest")
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.parent / (dest.name + ".staging-" + uuid.uuid4().hex)
    staging.mkdir()
    try:
        packed = dict(data)
        for key in ("science_bundle", "strategy_results", "phase_manifest"):
            entry = data.get(key)
            if entry is None:
                continue
            source = Path(entry["path"])
            if not source.is_absolute():
                source = source_manifest.parent / source
            name = key + source.suffix
            target = staging / name
            shutil.copyfile(source, target)
            if file_sha256(target) != entry["sha256"]:
                raise ValueError(f"{key} changed during package copy")
            packed[key] = {"path": name, "sha256": entry["sha256"]}
        manifest = staging / "grid-handoff.json"
        manifest.write_text(json.dumps(packed, sort_keys=True, indent=2), encoding="utf-8")
        verify_handoff(manifest)
        if dest.exists():
            raise FileExistsError(dest)
        staging.rename(dest)
        return dest / "grid-handoff.json"
    except BaseException:
        shutil.rmtree(staging)
        raise


def write_handoff(path,science_bundle_path,*,strategy_results_path=None,phase_manifest_path=None):
    science=Path(science_bundle_path)
    if not science.is_file():raise FileNotFoundError(science)
    if not science.stat().st_size:raise ValueError("science bundle is empty")
    dest=Path(path)
    if dest.resolve()==science.resolve():
        raise ValueError("handoff destination must not overwrite science bundle")
    out={
      "schema":1,
      "created_at":time.time(),
      "source":"strattester",
      "science_bundle":{"path":str(science.resolve()),"sha256":file_sha256(science)},
      "strategy_results":None,
      "phase_manifest":None,
      "ready_for_grid_import":True,
    }
    if strategy_results_path:
        p=Path(strategy_results_path)
        if p.is_file():out["strategy_results"]={"path":str(p.resolve()),"sha256":file_sha256(p)}
    if phase_manifest_path:
        p=Path(phase_manifest_path)
        if p.is_file():out["phase_manifest"]={"path":str(p.resolve()),"sha256":file_sha256(p)}
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(dest.suffix+".tmp")
    tmp.write_text(json.dumps(out,sort_keys=True,indent=2),encoding="utf-8")
    tmp.replace(dest)
    return out
