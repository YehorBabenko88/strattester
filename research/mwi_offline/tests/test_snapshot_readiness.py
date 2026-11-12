import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mwi_offline.snapshot_readiness import inspect_snapshot_bundle
from test_native_inspect import fixture, HEAD


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.snapshot = self.root/'snapshot.json'
        self.envelope = fixture()
        self.snapshot.write_text(json.dumps(self.envelope), encoding='utf-8')
        self.raw_hash = hashlib.sha256(self.snapshot.read_bytes()).hexdigest()
        self.manifest = dict(schema='mwi.snapshot.bundle.PROPOSAL.v1', dataset_id=self.envelope['dataset_id'],
                             dataset_fingerprint=self.envelope['dataset_fingerprint'], source_head=HEAD,
                             snapshot_sha256=self.raw_hash, references=dict(source_provenance=None,
                             source_owner_approval=None, external_artifact_admission=None))
        self.sidecar = self.root/'manifest.json'

    def tearDown(self): self.tmp.cleanup()

    def run_inspection(self):
        self.sidecar.write_text(json.dumps(self.manifest), encoding='utf-8')
        return inspect_snapshot_bundle(self.snapshot, self.raw_hash, HEAD, self.sidecar,
                                       hashlib.sha256(self.sidecar.read_bytes()).hexdigest())

    def test_absent_receipts_block_without_mutation(self):
        before = self.snapshot.read_bytes()
        result = self.run_inspection()
        self.assertFalse(result['training_eligible'])
        self.assertEqual(result['status'], 'REAL_DATA_TRAINING_BLOCKED')
        self.assertEqual(result['missingness']['ohlcv_gap_count'], 0)
        self.assertEqual(result['feature_coverage']['l2'], 'UNKNOWN')
        self.assertEqual(before, self.snapshot.read_bytes())

    def test_present_hash_references_never_become_authority(self):
        raw = b'{"claimed_approved":true}'
        (self.root/'claim.json').write_bytes(raw)
        ref = dict(file='claim.json', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        self.manifest['references'] = {k:ref for k in self.manifest['references']}
        result = self.run_inspection()
        self.assertFalse(result['training_eligible'])
        self.assertEqual(result['reference_integrity']['source_owner_approval'], 'HASH_VERIFIED_NOT_AUTHENTICATED')
        self.assertIn('OWNER_ADMISSION_VERIFIER_NOT_PROVISIONED', result['blockers'])

    def test_identity_mismatch_refused(self):
        self.manifest['dataset_id'] = '0'*64
        with self.assertRaises(ValueError): self.run_inspection()

    def test_reference_hash_and_path_refused(self):
        for name in ('../claim.json', 'claim.json'):
            self.manifest['references']['source_provenance'] = dict(file=name, bytes=1, sha256='a'*64)
            with self.assertRaises((ValueError, FileNotFoundError)): self.run_inspection()

    def test_no_self_issued_approval(self):
        self.manifest['approved'] = True
        with self.assertRaises(ValueError): self.run_inspection()


if __name__ == '__main__': unittest.main()
