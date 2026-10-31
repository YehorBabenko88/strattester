"""Actual pinned Math processes, synthetic Grid inputs, inert display output."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_grid_math_backtest_and_scientific_result_make_one_inert_display(tmp_path):
    from strattester.research.grid_math_history import canonical, digest, MathClient, replay, runtime_pin
    from strattester.research.history_joint import JointMathClient
    from strattester.research.history_terminan import review_packet
    from strattester.research.history_scientific_handoff import handoff_packet
    from strattester.research.history_joint_display import joint_display_packet
    root = Path(__file__).resolve().parents[3]
    grid = Path(os.environ.get('GRID_REFERENCE', root / 'bybit-cluster-grid'))
    math = Path(os.environ.get('MATH_REFERENCE', root / 'math'))
    if not (grid / 'grid/history_export_v11.py').exists() or not (math / 'python/history_scientific_worker.py').exists():
        if os.environ.get('HISTORY_REQUIRE_CROSSREPO') == '1':
            pytest.fail('required source-owner Grid/Math checkouts unavailable')
        pytest.skip('cross-repository source-owner checkouts not provisioned')
    from grid.history_export_v11 import export_records_v11
    spec = importlib.util.spec_from_file_location('composed_grid_fixture', grid / 'tests/test_history_export.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    rows, request, trust = fixture.fixture(80)
    # Synthetic upward gaps with falling candle bodies exercise nonempty OOS
    # execution for the frozen bearish analogue; this is no market claim.
    receipts = {}
    for row in rows:
        receipt = dict(trust['receipts'][row['dataset_fingerprint']])
        close = row['candle']['close']
        row['candle'].update(open=close + 1, high=close + 2, low=close - 1)
        row['dataset_fingerprint'] = digest({k: v for k, v in row.items() if k != 'dataset_fingerprint'})
        receipt['fingerprint'] = row['dataset_fingerprint']
        receipts[row['dataset_fingerprint']] = receipt
    trust['receipts'] = receipts
    trust['receipt_pins'] = {key: digest(value) for key, value in receipts.items()}
    dataset = export_records_v11(rows, request, trust)
    assert dataset['evidence_class'] == 'SYNTHETIC'
    policy = {'train_end_ms': 1800000, 'validation_end_ms': 3000000, 'test_end_ms': 4800000,
              'fee_bps': 5., 'slippage_bps': 2., 'notional': 100., 'starting_cash': 10000., 'latency_ms': 0,
              'funding_policy': 'EXPLICIT_PERPETUAL', 'funding_interval_ms': 60000, 'funding_anchor_ms': 0,
              'funding': [{'timestamp_ms': i * 60000, 'rate': .0001, 'mark_price': 100.} for i in range(80)],
              'model_version': 'grid-frozen-analog-v1'}
    def git(*args):
        return subprocess.check_output(['git', '-C', str(math), *args], text=True).strip()
    commit, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    with MathClient(math, commit, tree, runtime_pin(), timed=True) as client:
        backtest = replay(dataset, dataset['dataset_fingerprint'], client, policy)
    assert backtest['fills']
    assert backtest['splits']['test']['trades'] > 0
    assert backtest['completion_receipt'] == digest({k: v for k, v in backtest.items() if k != 'completion_receipt'})
    review = review_packet(backtest, backtest['completion_receipt'])
    history = handoff_packet(review, published_at_ms=4801000)
    trace = next(t for t in backtest['math_trace'] if t['decision_ms'] >= policy['train_end_ms'])
    graph = {'nodes': [{'id': 'twice', 'kind': 'formula', 'expression': 'x*2', 'outputUnit': 'USDT/BTC'}],
             'edges': [{'from': {'node': 'history', 'port': 'value'}, 'to': {'node': 'twice', 'port': 'x'}}],
             'outputs': [{'node': 'twice', 'port': 'value'}]}
    node = Path(shutil.which('node')).resolve()
    import hashlib
    with JointMathClient(math, commit, tree, runtime_pin(), node=str(node),
                         node_sha256=hashlib.sha256(node.read_bytes()).hexdigest()) as client:
        joint = client.compose(dataset, dataset['dataset_fingerprint'], trace['decision_ms'],
                               trace['train_count'], policy['train_end_ms'], graph)
    assert joint['scientific']['outputs'][0]['values'][0] == 202
    assert joint['history']['forecast'] == trace['forecast']
    assert joint['joint_request']['history']['dataset_id'] == dataset['dataset_id']
    display = joint_display_packet(history, joint['joint_request'], joint, joint['completion_receipt'],
                                   joint_published_at_ms=trace['decision_ms'] + 1000)
    assert display['schema'] == 'terminan.unified-display.v1'
    assert display['qualification'] == 'NOT_QUALIFIED'
    assert display['contract_only'] is True
    assert display['joint_result']['scientific']['schema'] == 'math.scientific.result.v2'
    assert display['history']['result_receipt'] == backtest['completion_receipt']
    assert display['history']['oos_metrics'] == backtest['splits']['test']['metrics']
    assert all(display[k] is False for k in ('training_authorized', 'execution_authority', 'trading_authorized'))
    output = Path(os.environ.get('HISTORY_EVIDENCE_ROOT', tmp_path)) / 'composed-runtime-display.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(display))
    assert json.loads(output.read_bytes()) == display
    terminan = Path(os.environ.get('TERMINAN_REFERENCE', root / 'Terminan'))
    if (terminan / 'terminan/unified_display.py').exists():
        import sys
        code = """import json,sys
sys.path.insert(0,sys.argv[1])
from pathlib import Path
from terminan.history_overlay import admit
result=admit(Path(sys.argv[2]).read_bytes(),allow_unified=True)
print(json.dumps(dict(qualification=result['qualification'],observations=len(result['observations']),
                     oos=result['oos'] is not None,scientific_proof=bool(result.get('scientific_proof')))))
"""
        response = subprocess.run([sys.executable, '-I', '-c', code, str(terminan), str(output)],
                                  check=True, capture_output=True, text=True, timeout=10)
        assert json.loads(response.stdout) == {'qualification': 'UNQUALIFIED_CONTRACT_ONLY',
                                              'observations': 80, 'oos': True, 'scientific_proof': True}
    elif os.environ.get('HISTORY_REQUIRE_CROSSREPO') == '1':
        pytest.fail('required Terminan unified display consumer unavailable')

