"""Offline research composition; operator pins are independent of input data."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strattester.research.grid_math_history import canonical
from strattester.research.history_joint import JointMathClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dataset', 'pins', 'math-root', 'graph', 'output'):
        parser.add_argument('--' + name, required=True)
    for name in ('decision-ms', 'train-end-ms', 'train-count'):
        parser.add_argument('--' + name, type=int, required=True)
    args = parser.parse_args()
    def read(path):
        with Path(path).open('rb') as f: raw = f.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024: raise ValueError('INPUT_LIMIT')
        return json.loads(raw)
    pins, d = read(args.pins), read(args.dataset)
    if d.get('dataset_id') != pins['dataset_id']: raise ValueError('DATASET_ID_PIN')
    with JointMathClient(args.math_root, pins['math_commit'], pins['math_tree'], pins['python_sha256'],
                         node=pins['node_executable'], node_sha256=pins['node_sha256']) as client:
        result = client.compose(d, pins['dataset_fingerprint'], args.decision_ms,
                                args.train_count, args.train_end_ms, read(args.graph))
    with Path(args.output).open('xb') as f: f.write(canonical(result))


if __name__ == '__main__': main()
