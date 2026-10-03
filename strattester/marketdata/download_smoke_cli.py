from pathlib import Path
import argparse,json
from dataclasses import asdict
from .download_smoke import run_download_smoke

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); p.add_argument('--minutes',type=int,default=10)
    a=p.parse_args(); r=run_download_smoke(Path(a.root),minutes=a.minutes)
    print(json.dumps(asdict(r),indent=2))
    return 0 if r.ok else 2
if __name__=='__main__': raise SystemExit(main())
