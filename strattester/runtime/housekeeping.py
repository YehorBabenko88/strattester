from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import time

@dataclass(frozen=True)
class CleanupReport:
    deleted:tuple[str,...]
    reclaimed_bytes:int
    skipped_active:tuple[str,...]

_ALLOWED_SUFFIXES=('.tmp','.part','.stage','.checkpoint.old')

def cleanup_artifacts(root,*,older_than_seconds=86400,limit=200,active_paths=(),now=None):
    """Delete only allowlisted stale artifacts under root; never follow symlinks."""
    root=Path(root).resolve();now=time.time() if now is None else float(now)
    age=float(older_than_seconds);limit=int(limit)
    if age<0 or limit<1:raise ValueError('invalid cleanup policy')
    active={Path(p).resolve() for p in active_paths}
    deleted=[];skipped=[];reclaimed=0
    if not root.exists():return CleanupReport((),0,())
    for p in sorted(root.rglob('*'),key=lambda x:str(x)):
        if len(deleted)>=limit:break
        if p.is_symlink() or not p.is_file():continue
        try:resolved=p.resolve()
        except OSError:continue
        if root not in resolved.parents:continue
        if resolved in active:
            skipped.append(str(resolved));continue
        if not any(p.name.endswith(s) for s in _ALLOWED_SUFFIXES):continue
        try:
            st=p.stat()
            if now-st.st_mtime<age:continue
            size=st.st_size;p.unlink();deleted.append(str(resolved));reclaimed+=size
        except FileNotFoundError:continue
    return CleanupReport(tuple(deleted),reclaimed,tuple(skipped))
