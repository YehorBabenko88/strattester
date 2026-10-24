import unittest
from research.alphafold_training.baselines import MeanReturnBaseline, RidgeBaseline

class BaselineTests(unittest.TestCase):
    def test_mean(self):
        model = MeanReturnBaseline().fit([(1.,), (2.,)], [.01, .03])
        self.assertAlmostEqual(model.predict([(100.,)])[0], .02)

    def test_ridge_deterministic(self):
        X = [(float(i), float(i % 3)) for i in range(20)]
        y = [0.01 * i for i in range(20)]
        a = RidgeBaseline(steps=100).fit(X, y)
        b = RidgeBaseline(steps=100).fit(X, y)
        self.assertEqual(a.predict(X), b.predict(X))

    def test_training_only_normalization(self):
        model = RidgeBaseline().fit([(1.,), (2.,)], [0., 1.])
        self.assertEqual(model.center, [1.5])
        model.predict([(1000000.,)])
        self.assertEqual(model.center, [1.5])

    def test_unfitted_and_schema_fail_closed(self):
        with self.assertRaises(ValueError):
            RidgeBaseline().predict([(1.,)])
        model = RidgeBaseline().fit([(1.,)], [0.])
        with self.assertRaises(ValueError):
            model.predict([(1., 2.)])

if __name__ == "__main__":
    unittest.main()
