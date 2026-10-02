from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .config import AppConfig
from .marketdata.discovery import discover_databases,inspect_database
from .persistence.sqlite_state_store import SQLiteStateStore

@dataclass(frozen=True)
class BootstrapResult:
    config:AppConfig
    market_db:Path|None
    state_db:Path
    mode:str

LEGACY_PATHS=(
    Path(r'C:\BybitBacktest\data\bybit_1m.sqlite3'),
    Path(r'C:\BybitTransfer\bybit_1m.sqlite3'),
    Path(r'C:\ProgramData\SQL\bybit_1m.sqlite3'),
)

def bootstrap(root:Path,legacy_paths=LEGACY_PATHS)->BootstrapResult:
    cfg=AppConfig.load(root); cfg.ensure_directories()
    configured=inspect_database(cfg.market_db)
    if configured.valid and configured.recognized_schema:
        market=configured.path; mode='configured'
    else:
        candidates=discover_databases(cfg,legacy_paths)
        recognized=[x for x in candidates if x.recognized_schema]
        market=recognized[0].path if recognized else None
        mode='legacy-readonly' if market else 'empty'
    state_path=cfg.state_dir/'strattester_state.sqlite3'
    state=SQLiteStateStore.open(state_path); state.close()
    return BootstrapResult(cfg,market,state_path,mode)
