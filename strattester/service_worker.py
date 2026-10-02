from pathlib import Path
from .config import AppConfig
from .doctor import run_doctor
def main():
    cfg=AppConfig.load(Path.cwd()); cfg.ensure_directories()
    report=run_doctor(cfg)
    if not report.python_supported or not report.paths_writable:return 2
    # Full runtime wiring is activated by the scheduler bootstrap layer.
    return 0
if __name__=='__main__': raise SystemExit(main())
