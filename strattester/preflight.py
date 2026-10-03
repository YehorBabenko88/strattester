from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import importlib.util,os,sqlite3,sys
from .bootstrap import bootstrap
from .config import AppConfig
from .remote.tailscale import detect_tailscale

@dataclass(frozen=True)
class Check:
    name:str; ok:bool; required:bool; detail:str

@dataclass(frozen=True)
class PreflightReport:
    checks:tuple[Check,...]
    @property
    def required_ok(self): return all(x.ok for x in self.checks if x.required)

def run_preflight(root:Path,check_network:bool=False)->PreflightReport:
    root=Path(root)
    cfg=AppConfig.load(root); checks=[]
    checks.append(Check('python',sys.version_info>=(3,11),True,sys.version.split()[0]))
    checks.append(Check('package_import',importlib.util.find_spec('strattester') is not None,True,'strattester'))
    try:
        cfg.ensure_directories()
        probe=cfg.state_dir/'.preflight'; probe.write_text('ok',encoding='utf-8'); probe.unlink()
        checks.append(Check('directories',True,True,str(cfg.root)))
    except OSError as exc: checks.append(Check('directories',False,True,str(exc)))
    try:
        b=bootstrap(root)
        con=sqlite3.connect(f'file:{b.state_db.as_posix()}?mode=ro',uri=True)
        try: ok=str(con.execute('PRAGMA quick_check').fetchone()[0]).lower()=='ok'
        finally: con.close()
        checks.append(Check('sqlite_state',ok,True,str(b.state_db)))
        checks.append(Check('market_db',b.market_db is not None,False,b.mode))
    except Exception as exc:
        checks.append(Check('sqlite_state',False,True,str(exc)))
        checks.append(Check('market_db',False,False,'bootstrap failed'))
    checks.append(Check('telegram',bool(cfg.telegram_token and cfg.telegram_chat_id),False,
                        'configured' if cfg.telegram_token and cfg.telegram_chat_id else 'not configured'))
    ts=detect_tailscale()
    checks.append(Check('tailscale',ts.installed and ts.running,False,ts.detail))
    if check_network:
        checks.append(Check('network',False,False,'network probe not implemented yet'))
    return PreflightReport(tuple(checks))
