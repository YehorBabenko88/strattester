import hashlib
import tempfile
import unittest
from pathlib import Path
from research.alphafold_training.evaluation import Sample
from research.alphafold_training.runner import (
    ResearchConfig, evaluate_offline, verify_artifact,
)

class ConstantModel:
    def fit(self, X, y):
        self.value = sum(y) / len(y)
    def predict(self, X):
        return [self.value] * len(X)

class RunnerTests(unittest.TestCase):
    def test_offline_evaluation(self):
        rows = [Sample("BTC", t, t + 1, t, (float(t),), .001)
                for t in (1, 3, 5, 11, 13, 15, 21, 23, 25)]
        result = evaluate_offline(rows, ConstantModel, ResearchConfig(10, 20, 30))
        self.assertEqual(result["status"], "RESEARCH_UNVERIFIED")
        self.assertEqual(result["test"]["count"], 3)
        self.assertEqual(result["zero_baseline"]["mean_net_return"], 0)

    def test_validation_predict_called_before_test_predict(self):
        calls = []
        class TrackingModel:
            def fit(self, X, y):
                calls.append(("fit", len(X)))
            def predict(self, X):
                calls.append(("predict", len(X)))
                return [0.001] * len(X)
        rows = [Sample("BTC", t, t + 1, t, (float(t),), .001)
                for t in (1, 3, 5, 11, 13, 15, 21, 23, 25, 27)]
        evaluate_offline(rows, TrackingModel, ResearchConfig(10, 20, 30))
        self.assertEqual(calls, [("fit", 3), ("predict", 3), ("predict", 4)])

    def test_overlap_rejected(self):
        rows = [Sample("BTC", t, t + 3, t, (1.,), .01)
                for t in (1, 5, 11, 12, 21, 25)]
        with self.assertRaises(ValueError):
            evaluate_offline(rows, ConstantModel, ResearchConfig(10, 20, 30))

    def test_artifact_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "model.bin"
            p.write_bytes(b"model")
            digest = hashlib.sha256(b"model").hexdigest()
            self.assertTrue(verify_artifact(p, digest))
            p.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                verify_artifact(p, digest)

if __name__ == "__main__":
    unittest.main()
