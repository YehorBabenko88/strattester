from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil
import sqlite3
from typing import Sequence
from .integrity import quick_check

@dataclass(frozen=True)
class DatabaseCandidate:
    path: Path
    valid: bool
    recognized_schema: bool
    size_bytes: int
    latest_timestamp: int | None

@dataclass(frozen=True)
class DatabaseInspection(DatabaseCandidate):
    error: str | None = None

@dataclass(frozen=True)
class AdoptionResult:
    adopted: bool
    destination: Path
    reason: str

def inspect_database(path: Path) -> DatabaseInspection:
    path=Path(path)
    if not path.is_file():
        return DatabaseInspection(path,False,False,0,None,'missing')
    integrity=quick_check(path)
    if not integrity.ok:
        return DatabaseInspection(path,False,False,path.stat().st_size,None,integrity.message)
    try:
        con=sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True)
        try:
            tables={r[0] for r in con.execute("select name from sqlite_master where type='table'")}
            recognized='candles' in tables
            latest=None
            if recognized:
                cols={r[1] for r in con.execute('pragma table_info(candles)')}
                ts_col='open_time' if 'open_time' in cols else ('open_time_ms' if 'open_time_ms' in cols else None)
                if ts_col:
                    latest=con.execute(f'select max({ts_col}) from candles').fetchone()[0]
        finally: con.close()
        return DatabaseInspection(path,True,recognized,path.stat().st_size,latest,None)
    except sqlite3.Error as exc:
        return DatabaseInspection(path,False,False,path.stat().st_size,None,str(exc))

def discover_databases(config, extra_paths: Sequence[Path]=()) -> list[DatabaseCandidate]:
    paths=[]
    for p in [config.market_db,*extra_paths]:
        p=Path(p)
        if p not in paths: paths.append(p)
    items=[inspect_database(p) for p in paths]
    valid=[x for x in items if x.valid]
    return sorted(valid,key=lambda x:(x.recognized_schema,x.latest_timestamp or -1,x.size_bytes),reverse=True)

def adopt_database(candidate: DatabaseCandidate, destination: Path) -> AdoptionResult:
    destination=Path(destination)
    if not candidate.valid:
        return AdoptionResult(False,destination,'invalid source')
    if destination.exists():
        return AdoptionResult(False,destination,'destination exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(candidate.path,destination)
    check=quick_check(destination)
    if not check.ok:
        destination.unlink(missing_ok=True)
        return AdoptionResult(False,destination,'copied database failed integrity check')
    return AdoptionResult(True,destination,'adopted')
