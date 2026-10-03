from pathlib import Path
import argparse,json
from dataclasses import asdict
from .smoke import run_worker_smoke

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',default='.')
    a=p.parse_args(); r=run_worker_smoke(Path(a.root))
    print(json.dumps(asdict(r),indent=2))
    return 0 if r.ok else 2
if __name__=='__main__': raise SystemExit(main())
