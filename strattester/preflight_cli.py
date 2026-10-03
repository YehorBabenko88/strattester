from pathlib import Path
import argparse,json
from dataclasses import asdict
from .preflight import run_preflight

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); p.add_argument('--network',action='store_true')
    a=p.parse_args(); report=run_preflight(Path(a.root),check_network=a.network)
    print(json.dumps({'required_ok':report.required_ok,'checks':[asdict(x) for x in report.checks]},indent=2))
    return 0 if report.required_ok else 2
if __name__=='__main__': raise SystemExit(main())
