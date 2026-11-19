import argparse,json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from .smoke import run_worker_smoke

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root', type=Path, help='Existing parent for a disposable smoke directory')
    a=p.parse_args()
    with TemporaryDirectory(prefix='strattester-smoke-', dir=a.root) as root:
        r=run_worker_smoke(Path(root))
    print(json.dumps(asdict(r),indent=2))
    return 0 if r.ok else 2
if __name__=='__main__': raise SystemExit(main())
