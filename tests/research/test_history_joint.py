import copy
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import unittest
_spec = importlib.util.spec_from_file_location('joint_history_fixture',
    pathlib.Path(__file__).with_name('test_grid_math_history_v11.py'))
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)
dataset, client, policy, MATH = _fixture.dataset, _fixture.client, _fixture.policy, _fixture.MATH
from strattester.research.grid_math_history import digest, runtime_pin


def graph():
    return {'nodes': [{'id': 'twice', 'kind': 'formula', 'expression': 'x*2', 'outputUnit': 'USDT/BTC'},
                      {'id': 'model', 'kind': 'model', 'model': 'affine', 'parameters': {'gain': 2, 'offset': 0}},
                      {'id': 'comparison', 'kind': 'compare'}],
            'edges': [{'from': {'node': 'history', 'port': 'value'}, 'to': {'node': n, 'port': 'x'}}
                      for n in ('twice', 'model')] + [
                {'from': {'node': 'twice', 'port': 'value'}, 'to': {'node': 'comparison', 'port': 'a'}},
                {'from': {'node': 'model', 'port': 'value'}, 'to': {'node': 'comparison', 'port': 'b'}}],
            'outputs': [{'node': 'twice', 'port': 'value'}, {'node': 'comparison', 'port': 'mae'}]}


def joint_client(**overrides):
    from strattester.research.history_joint import JointMathClient
    def git(*args): return subprocess.check_output(['git', '-C', str(MATH), *args], text=True).strip()
    node = pathlib.Path(shutil.which('node')).resolve()
    kw = {'node': str(node), 'node_sha256': hashlib.sha256(node.read_bytes()).hexdigest()}
    kw.update(overrides)
    return JointMathClient(MATH, git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}'), runtime_pin(), **kw)


class JointIntegration(unittest.TestCase):
    def test_supported_two_thousand_row_snapshot_returns_bounded_complete_result(self):
        from grid.history_export_v11 import export_records_v11
        rows, request, trust = _fixture.fixture.fixture(2000)
        d = export_records_v11(rows, request, trust)
        with joint_client() as c:
            r = c.compose(d, d['dataset_fingerprint'], 120000000, 30, 1800000, graph())
        self.assertEqual(len(r['provenance']['rows']), 2000)
        self.assertEqual(len(r['scientific']['outputs'][0]['values']), 2000)
        self.assertLess(len(json.dumps(r).encode()), 4 * 1024 * 1024)

    def test_normal_eighty_minute_result_is_not_cut_off_by_legacy_limit(self):
        d = dataset()
        with joint_client() as c:
            r = c.compose(d, d['dataset_fingerprint'], 4800000, 30, 1800000, graph())
        self.assertEqual(len(r['provenance']['rows']), 80)
        self.assertEqual(len(r['scientific']['outputs'][0]['values']), 80)
        self.assertEqual(r['history']['forecast_target_event_end_ms'], 4860000)

    def test_both_engines_use_one_source_and_preserve_delayed_clocks(self):
        d = dataset(); decision = 40 * 60000 + 500
        d['rows'][39]['available_at_ms'] += 500
        from grid.history_export_v11 import dataset_content
        d['dataset_id'] = digest(dataset_content(d))
        d['dataset_fingerprint'] = digest({k: v for k, v in d.items() if k != 'dataset_fingerprint'})
        with joint_client() as c:
            r = c.compose(d, d['dataset_fingerprint'], decision, 30, 1800000, graph())
            with client() as old:
                ref = old.predict_timed(d['rows'][:40], d, decision, 30, 1800000, 'grid-frozen-analog-v1')
            self.assertEqual(r['history'], ref)
            self.assertEqual(r['scientific']['outputs'][0]['values'][:3], [202, 202.2, 202.4])
            self.assertEqual(r['scientific']['outputs'][0]['timestamps'][-1], 2400000)
            self.assertEqual(r['scientific']['outputs'][0]['availableAt'][-1], 2400500)
            self.assertEqual(r['scientific']['outputs'][1]['values'], [0])
            self.assertEqual(r['math_source']['commit'], c.commit)
            self.assertEqual(r['math_source']['tree'], c.tree)
            self.assertTrue(any(k.startswith('src/') for k in r['math_source']['manifest']))
            self.assertTrue(any(k.startswith('python/') for k in r['math_source']['manifest']))
            self.assertFalse(r['execution_authority'])

    def test_future_suffix_cannot_change_decision_outputs(self):
        d = dataset(); other = copy.deepcopy(d)
        other['rows'][-1]['close'] += .25
        from grid.history_export_v11 import dataset_content
        other['dataset_id'] = digest(dataset_content(other))
        other['dataset_fingerprint'] = digest({k: v for k, v in other.items() if k != 'dataset_fingerprint'})
        with joint_client() as c:
            a = c.compose(d, d['dataset_fingerprint'], 2400000, 30, 1800000, graph())
            b = c.compose(other, other['dataset_fingerprint'], 2400000, 30, 1800000, graph())
        self.assertEqual(a['scientific'], b['scientific'])
        self.assertEqual(a['history']['forecast'], b['history']['forecast'])
        self.assertEqual(a['history']['prefix_digest'], b['history']['prefix_digest'])

    def test_wrong_runtime_dataset_source_and_injected_graph_reject(self):
        with self.assertRaises(ValueError):
            with joint_client(node_sha256='0' * 64): pass
        d = dataset()
        with joint_client() as c:
            with self.assertRaises(ValueError): c.compose(d, '0' * 64, 2400000, 30, 1800000, graph())
            bad = graph(); bad['nodes'].append({'id': 'injected', 'kind': 'source'})
            with self.assertRaises(ValueError): c.compose(d, d['dataset_fingerprint'], 2400000, 30, 1800000, bad)
            with self.assertRaises(ValueError): c.compose(d, d['dataset_fingerprint'], 2400000, 30, 60000, graph())
            # Any alteration of the immutable staged JS source fails before execution.
            target = c.path / 'joint/src/scientific-engine.mjs'
            target.write_text('throw Error("tampered")')
            with self.assertRaises(ValueError): c.compose(d, d['dataset_fingerprint'], 2400000, 30, 1800000, graph())
