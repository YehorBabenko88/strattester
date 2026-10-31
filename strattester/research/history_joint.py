"""One immutable Math source for both APIs; no local numerical computation."""
import hashlib
import copy
from pathlib import Path, PurePosixPath
import subprocess
from .grid_math_history import MathClient, admit, digest


class JointMathClient(MathClient):
    MAX_OUTPUT_LIMIT = 4 * 1024 * 1024

    def __init__(self, root, commit, tree, python_sha256, *, node, node_sha256, **kw):
        kw.setdefault('output_limit', self.MAX_OUTPUT_LIMIT)
        super().__init__(root, commit, tree, python_sha256, timed=True, **kw)
        self.node = str(Path(node).resolve())
        self.node_sha256 = node_sha256

    def _node_pin(self):
        if hashlib.sha256(Path(self.node).read_bytes()).hexdigest() != self.node_sha256:
            raise ValueError('NODE_RUNTIME_PIN')

    def __enter__(self):
        super().__enter__()
        try:
            self._node_pin()
            # A single commit supplies every Python/JS dependency, never two checkouts.
            entries = []
            for line in self.git('ls-tree', '-r', '-z', '-l', self.commit, '--', 'python', 'src', 'scripts/history').split(b'\0'):
                if not line: continue
                metadata, name = line.split(b'\t', 1)
                mode, kind, oid, size = metadata.split()
                p = PurePosixPath(name.decode())
                if (mode not in (b'100644', b'100755') or kind != b'blob' or p.is_absolute()
                        or '..' in p.parts or p.suffix not in ('.py', '.mjs') or int(size) > 2 * 1024 * 1024):
                    raise ValueError('SOURCE_MEMBER')
                entries.append((str(p), oid, int(size)))
            if sum(size for _, _, size in entries) > 16 * 1024 * 1024: raise ValueError('SOURCE_LIMIT')
            # cat-file returns raw blob bytes; git archive may apply autocrlf conversions.
            batch = subprocess.check_output(['git', '--no-replace-objects', '-C', str(self.root), 'cat-file', '--batch'],
                input=b''.join(oid + b'\n' for _, oid, _ in entries), timeout=10, stderr=subprocess.DEVNULL)
            self.joint_manifest = {}
            offset = 0
            for name, oid, size in entries:
                end = batch.index(b'\n', offset)
                actual_oid, kind, actual_size = batch[offset:end].split()
                if actual_oid != oid or kind != b'blob' or int(actual_size) != size: raise ValueError('BLOB_HEADER')
                data = batch[end + 1:end + 1 + size]; offset = end + size + 2
                target = self.path / 'joint' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                self.joint_manifest[name] = hashlib.sha256(data).hexdigest()
            if offset != len(batch): raise ValueError('BLOB_TRAILING_BYTES')
            required = ('python/history_scientific_worker.py', 'python/history_timed_worker.py',
                        'scripts/history/scientific-stdio.mjs', 'src/scientific-engine.mjs')
            if any(f not in self.joint_manifest for f in required):
                raise ValueError('BOTH_APIS_REQUIRED')
            return self
        except BaseException:
            super().__exit__(None, None, None)
            raise

    def compose(self, dataset, expected_pin, decision_ms, train_count, train_end_ms, graph):
        d = admit(dataset, expected_pin)
        if d['schema'] != 'grid.history.v1.1': raise ValueError('TIMED_DATASET_REQUIRED')
        if type(decision_ms) is not int or not 0 <= decision_ms <= d['request']['as_of_ms']:
            raise ValueError('DECISION_CLOCK')
        # Keep a contiguous known prefix; do not skip a late observation and bridge a gap.
        rows = []
        for row in d['rows']:
            if row['event_end_ms'] > decision_ms or row['available_at_ms'] > decision_ms: break
            rows.append(row)
        h = {'schema': 'math.history.request.v1.1', 'rows': rows, 'dataset_id': d['dataset_id'],
             'dataset_fingerprint': expected_pin, 'source': d['source'],
             'market': {k: d['request'][k] for k in ('venue', 'market_type', 'symbol')},
             'units': d['request']['units'], 'decision_ms': decision_ms, 'train_count': train_count,
             'train_end_ms': train_end_ms, 'max_age_ms': d['request']['max_age_ms'],
             'model_version': 'grid-frozen-analog-v1'}
        q = {'schema': 'math.history.scientific.request.v1', 'history': h, 'graph': graph}
        self._node_pin()
        for name, pin in self.joint_manifest.items():
            if hashlib.sha256((self.path / 'joint' / name).read_bytes()).hexdigest() != pin:
                raise ValueError('JOINT_SOURCE_TAMPER')
        r = self._execute(q, 'joint/python/history_scientific_worker.py', 2 * 1024 * 1024, (self.node,))
        if (r.get('schema') != 'math.history.scientific.result.v1' or r.get('request_digest') != digest(q)
                or r.get('api_revision') != 'history-1.1+scientific-2.1'
                or any(r.get(k) is not False for k in ('training_authorized', 'execution_authority', 'trading_authorized'))
                or r.get('provenance') != {k: h[k] for k in ('dataset_id', 'dataset_fingerprint',
                                             'source', 'market', 'units', 'decision_ms', 'rows')}
                or r.get('history', {}).get('prefix_digest') != digest(rows)
                or r.get('scientific', {}).get('schema') != 'math.scientific.result.v2'):
            raise ValueError('JOINT_RESULT_BINDING')
        r['math_source'] = {'commit': self.commit, 'tree': self.tree, 'manifest': dict(self.joint_manifest),
                            'python_sha256': self.python_sha256, 'node_sha256': self.node_sha256}
        r['joint_request'] = copy.deepcopy(q)
        r['completion_receipt'] = digest(r)
        return r
