"""Offline historical replay. Pins file is independently provisioned policy."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strattester.research.grid_math_history import MathClient, replay, canonical

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','policy','pins','math-root','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args()
    def read(path):
        with Path(path).open('rb') as f:b=f.read(8*1024*1024+1)
        if len(b)>8*1024*1024:raise ValueError('INPUT_LIMIT')
        return json.loads(b)
    pins=read(a.pins)
    dataset=read(a.dataset)
    if dataset.get('schema')!='grid.history.v1.1' or dataset.get('dataset_id')!=pins['dataset_id']:
        raise ValueError('TIMED_DATASET_REQUIRED')
    with MathClient(a.math_root,pins['math_commit'],pins['math_tree'],pins['python_sha256'],timed=True) as client:
        result=replay(dataset,pins['dataset_fingerprint'],client,read(a.policy))
    # No partial result is written on admission/computation failure.
    target=Path(a.output)
    with target.open('xb') as f:f.write(canonical(result))

if __name__=='__main__':main()
