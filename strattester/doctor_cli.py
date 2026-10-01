from pathlib import Path
from .config import AppConfig
from .doctor import run_doctor
def main():
    r=run_doctor(AppConfig.load(Path.cwd()))
    return 0 if r.python_supported and r.paths_writable else 2
if __name__=='__main__': raise SystemExit(main())
