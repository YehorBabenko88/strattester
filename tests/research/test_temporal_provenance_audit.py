import unittest
from dataclasses import replace
from research.alphafold_training.temporal_provenance_audit import (
    TemporalObservation, audit_temporal_observations,
)

class TemporalProvenanceAuditTests(unittest.TestCase):
    def setUp(self):
        self.row = TemporalObservation("SOLUSDT", 60, 100, 160, 99, 100, "signed-epoch")

    def test_valid_provenance(self):
        self.assertEqual(audit_temporal_observations([self.row])["count"], 1)

    def test_future_feature_rejected(self):
        with self.assertRaises(ValueError):
            audit_temporal_observations([replace(self.row, feature_available_ns=101)])

    def test_future_revision_rejected(self):
        with self.assertRaises(ValueError):
            audit_temporal_observations([replace(self.row, revision_available_ns=101)])

    def test_instrument_holdout(self):
        with self.assertRaises(ValueError):
            audit_temporal_observations([self.row], held_out_instruments={"SOLUSDT"})

    def test_timeframe_holdout(self):
        with self.assertRaises(ValueError):
            audit_temporal_observations([self.row], held_out_timeframes={60})

    def test_duplicate_identity(self):
        with self.assertRaises(ValueError):
            audit_temporal_observations([self.row, self.row])

if __name__ == "__main__":
    unittest.main()
