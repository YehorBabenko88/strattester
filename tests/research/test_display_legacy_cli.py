"""Replay a recorded legacy export through the real CLI, not through Math."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'tests/fixtures/history-replay-contract.v1.json'

class LegacyDisplayCLI(unittest.TestCase):
    def test_review_retains_recorded_publication_clock(self):
        from strattester.research.history_terminan import review_packet
        from strattester.research.grid_math_history import digest
        source=json.loads(FIXTURE.read_bytes());source['published_at_ms']=4801000
        source['completion_receipt']=digest({k:v for k,v in source.items() if k!='completion_receipt'})
        r=review_packet(source,source['completion_receipt'])
        self.assertEqual(r['published_at_ms'],4801000)

    def test_real_review_and_cli_preserve_legacy_values_and_explicit_publication(self):
        receipt=json.loads(FIXTURE.with_name('history-replay-contract.receipt.json').read_bytes())
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),receipt['sha256'])
        source=json.loads(FIXTURE.read_bytes())
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'packet.json'
            command=[sys.executable,'scripts/export_history_scientific_handoff.py','--input',str(FIXTURE),
                '--receipt-pin',source['completion_receipt'],'--published-at-ms','4801000','--output',str(target)]
            env={**os.environ,'PYTHONPATH':str(ROOT)}
            subprocess.run(command,cwd=ROOT,env=env,check=True,capture_output=True)
            p=json.loads(target.read_bytes())
            self.assertEqual(p['market'],source['market']);self.assertEqual(p['model'],source['math'])
            self.assertEqual(p['model_version'],source['model_version']);self.assertEqual(p['units'],source['units'])
            self.assertEqual(p['oos_available_at_ms'],4801000)
            self.assertEqual([x['value'] for x in p['forecast_points']],[x['forecast'] for x in source['math_trace']])
            self.assertEqual(len(p['forecast_points']),60)
            self.assertEqual(p['source']['snapshot_fingerprint'],source['dataset_fingerprint'])
            self.assertEqual(p['oos_metrics'],source['splits']['test']['metrics'])
            self.assertNotEqual(subprocess.run(command,cwd=ROOT,env=env,capture_output=True).returncode,0)  # exclusive creation
