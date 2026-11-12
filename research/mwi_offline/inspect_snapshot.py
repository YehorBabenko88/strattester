"""Inspect a supplied native Grid v1.1 FILE without granting training eligibility."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mwi_offline.native_inspect import inspect_grid_v11

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--file',required=True);p.add_argument('--sha256',required=True);p.add_argument('--source-head',required=True)
    args=p.parse_args()
    print(json.dumps(inspect_grid_v11(args.file,args.sha256,args.source_head),sort_keys=True,indent=2))

if __name__=='__main__':main()
