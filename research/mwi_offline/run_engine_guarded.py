"""One fixed research child with a 60-second parent timeout; no scheduler."""
from pathlib import Path
import subprocess
import sys


def guarded(arguments):
    command=[sys.executable,'-I','-S','-B',str(Path(__file__).with_name('run_engine_cycle.py'))]+list(arguments)
    try:return subprocess.run(command,timeout=60,check=False).returncode
    except subprocess.TimeoutExpired:
        print('RESEARCH_WALL_TIMEOUT: child stopped; preserve checkpoint and inspect before resume',file=sys.stderr)
        return 124


if __name__=='__main__':raise SystemExit(guarded(sys.argv[1:]))
