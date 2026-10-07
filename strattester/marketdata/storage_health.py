from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil,sqlite3,time
from .integrity import quick_check

@dataclass(frozen=True)
class StorageHealth:
    ok:bool
    writable:bool
    free_bytes:int
    integrity_ok:bool
    message:str=''

def storage_health(path:Path,min_free_bytes:int=2*1024**3)->StorageHealth:
    path=Path(path)
    base=path if path.is_dir() else path.parent
    try:
        free=shutil.disk_usage(base).free
    except OSError as exc:
        return StorageHealth(False,False,0,False,str(exc))
    if free<min_free_bytes:
        return StorageHealth(False,False,free,True,'insufficient disk space')
    if path.is_file():
        integrity=quick_check(path)
        if not integrity.ok:
            return StorageHealth(False,False,free,False,integrity.message)
    probe=base/f'.strattester-write-probe-{time.time_ns()}'
    try:
        with open(probe,'wb') as fh:
            fh.write(b'ok'); fh.flush()
        probe.unlink(missing_ok=True)
    except OSError as exc:
        probe.unlink(missing_ok=True)
        return StorageHealth(False,False,free,True,str(exc))
    return StorageHealth(True,True,free,True,'')

def quarantine_database(path:Path,quarantine_dir:Path)->Path:
    path=Path(path); quarantine_dir=Path(quarantine_dir)
    if not path.is_file(): raise FileNotFoundError(path)
    check=quick_check(path)
    if check.ok: raise ValueError('refusing to quarantine a healthy database')
    quarantine_dir.mkdir(parents=True,exist_ok=True)
    stamp=int(time.time())
    target=quarantine_dir/f'{path.name}.corrupt-{stamp}'
    path.replace(target)
    for suffix in ('-wal','-shm'):
        side=Path(str(path)+suffix)
        if side.exists():
            side.replace(Path(str(target)+suffix))
    return target
