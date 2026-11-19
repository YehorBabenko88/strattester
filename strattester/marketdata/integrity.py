from dataclasses import dataclass
from pathlib import Path
import sqlite3

@dataclass(frozen=True)
class IntegrityResult:
    ok: bool
    message: str

def connect_read_only(path: Path) -> sqlite3.Connection:
    uri = Path(path).resolve().as_uri()
    return sqlite3.connect(f'{uri}?mode=ro', uri=True)


def quick_check(path: Path) -> IntegrityResult:
    path=Path(path)
    if not path.is_file():
        return IntegrityResult(False,'missing')
    try:
        con=connect_read_only(path)
        try:
            msg=str(con.execute('PRAGMA quick_check').fetchone()[0])
        finally:
            con.close()
        return IntegrityResult(msg.lower()=='ok',msg)
    except sqlite3.Error as exc:
        return IntegrityResult(False,str(exc))
