from pathlib import Path
import os,time
from .config import AppConfig
from .doctor import run_doctor
from .runtime.logging import build_logger
from .runtime.phase_manifest import PhaseManifest

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
    phase=PhaseManifest(cfg.state_dir/'phase-manifest.json')
    while True:
        _heartbeat(heartbeat)
        # Keep the service liveness loop independent from heavy research jobs.
        # Historical executors update durable job state elsewhere; this process
        # never fabricates completion and never advances phases on heartbeat alone.
        current=phase.load()
        if current.get("corrupt"):
            log.error('phase manifest corrupt')
        time.sleep(10)
if __name__=='__main__': raise SystemExit(main())
