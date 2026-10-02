from pathlib import Path
import os,time
from .config import AppConfig
from .doctor import run_doctor
from .runtime.logging import build_logger

def _heartbeat(path:Path):
    tmp=path.with_suffix('.tmp'); tmp.write_text(str(time.time()),encoding='utf-8'); os.replace(tmp,path)

def main():
    cfg=AppConfig.load(Path.cwd()); cfg.ensure_directories()
    log=build_logger(cfg.logs_dir/'worker.jsonl','strattester.worker')
    report=run_doctor(cfg)
    if not report.python_supported or not report.paths_writable:
        log.error('startup doctor failed'); return 2
    log.info('worker service started')
    heartbeat=cfg.state_dir/'worker-heartbeat'
    while True:
        _heartbeat(heartbeat)
        # Runtime job orchestration is attached here; heartbeat deliberately remains
        # independent so the controller can distinguish a dead service from idle work.
        time.sleep(10)
if __name__=='__main__': raise SystemExit(main())
