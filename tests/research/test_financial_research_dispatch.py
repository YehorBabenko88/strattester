import unittest
from unittest.mock import patch
from strattester.research.financial_contract import Instrument
from strattester.research.financial_research_spec import FinancialResearchSpec
from strattester.research.financial_research_dispatch import predict_research_only

class FinancialResearchDispatchTests(unittest.TestCase):
    def setUp(self):
        self.instrument = Instrument("bybit", "linear", "SOLUSDT")
        self.spec = FinancialResearchSpec((self.instrument,), 60, 300, "v1")

    def test_reject_legacy_data_before_model_loading(self):
        with patch("strattester.research.financial_research_dispatch.load_checkpoint") as loader:
            with self.assertRaises(ValueError):
                predict_research_only(self.spec, object(), instrument=self.instrument,
                                      model_path="ignored", model_sha256="0" * 64,
                                      timeframe_ns=60, horizon_ns=300, available_ns=1)
            loader.assert_not_called()

    def test_reject_unlisted_instrument_before_model_loading(self):
        other = Instrument("bybit", "linear", "ETHUSDT")
        with patch("strattester.research.financial_research_dispatch.load_checkpoint") as loader:
            with self.assertRaises(ValueError):
                predict_research_only(self.spec, object(), instrument=other,
                                      model_path="ignored", model_sha256="0" * 64,
                                      timeframe_ns=60, horizon_ns=300, available_ns=1)
            loader.assert_not_called()

    def test_unapproved_cross_timeframe_context_rejected(self):
        class FakeSnapshot:
            origin_ns = 100
            bars = (type("Bar", (), {"instrument": Instrument("bybit", "linear", "SOLUSDT"),
                                     "timeframe_ns": 300})(),)
            def validate(self):
                return self
        with patch("strattester.research.financial_research_dispatch.Snapshot", FakeSnapshot):
            with patch("strattester.research.financial_research_dispatch.load_checkpoint") as loader:
                with self.assertRaises(ValueError):
                    predict_research_only(self.spec, FakeSnapshot(), instrument=self.instrument,
                                          model_path="ignored", model_sha256="0" * 64,
                                          timeframe_ns=60, horizon_ns=300, available_ns=100)
                loader.assert_not_called()

    def test_unlisted_context_instrument_rejected_before_loading(self):
        class FakeSnapshot:
            origin_ns = 100
            bars = (type("Bar", (), {"instrument": Instrument("bybit", "linear", "ETHUSDT"),
                                     "timeframe_ns": 60})(),)
            def validate(self):
                return self
        with patch("strattester.research.financial_research_dispatch.Snapshot", FakeSnapshot):
            with patch("strattester.research.financial_research_dispatch.load_checkpoint") as loader:
                with self.assertRaises(ValueError):
                    predict_research_only(self.spec, FakeSnapshot(), instrument=self.instrument,
                                          model_path="ignored", model_sha256="0" * 64,
                                          timeframe_ns=60, horizon_ns=300, available_ns=100)
                loader.assert_not_called()

    def test_missing_target_timeframe_rejected_before_loading(self):
        class FakeSnapshot:
            origin_ns = 100
            bars = ()
            def validate(self):
                return self
        with patch("strattester.research.financial_research_dispatch.Snapshot", FakeSnapshot):
            with patch("strattester.research.financial_research_dispatch.load_checkpoint") as loader:
                with self.assertRaises(ValueError):
                    predict_research_only(self.spec, FakeSnapshot(), instrument=self.instrument,
                                          model_path="ignored", model_sha256="0" * 64,
                                          timeframe_ns=60, horizon_ns=300, available_ns=100)
                loader.assert_not_called()

    def test_backdated_availability_rejected_before_loading(self):
        from unittest.mock import patch
        class FakeSnapshot:
            origin_ns = 100
            bars = (type("Bar", (), {"instrument": Instrument("bybit", "linear", "SOLUSDT"), "timeframe_ns": 60})(),)
            def validate(self):
                return self
        # Enforce the exact Snapshot type through an autospec-like object
        # while keeping the test free from heavyweight market fixtures.
        with patch("strattester.research.financial_research_dispatch.Snapshot", FakeSnapshot):
            with patch("strattester.research.financial_research_dispatch.load_checkpoint") as loader:
                with self.assertRaises(ValueError):
                    predict_research_only(self.spec, FakeSnapshot(), instrument=self.instrument,
                                          model_path="ignored", model_sha256="0" * 64,
                                          timeframe_ns=60, horizon_ns=300, available_ns=99)
                loader.assert_not_called()

    def test_malformed_checkpoint_metadata_rejected(self):
        class FakeSnapshot:
            origin_ns = 100
            def validate(self):
                return self
        class FakeModel:
            class config:
                horizon_ns = 300
        with patch("strattester.research.financial_research_dispatch.Snapshot", FakeSnapshot):
            with patch("strattester.research.financial_research_dispatch.load_checkpoint",
                       return_value=(FakeModel(), {"config": None})):
                with patch("strattester.research.financial_research_dispatch.predict_snapshot") as predictor:
                    with self.assertRaises(ValueError):
                        predict_research_only(self.spec, FakeSnapshot(), instrument=self.instrument,
                                              model_path="ignored", model_sha256="0" * 64,
                                              timeframe_ns=60, horizon_ns=300, available_ns=100)
                    predictor.assert_not_called()

    def test_reject_live_spec(self):
        live = FinancialResearchSpec((self.instrument,), 60, 300, "v1", enabled=True)
        with self.assertRaises(ValueError):
            predict_research_only(live, object(), instrument=self.instrument,
                                  model_path="ignored", model_sha256="0" * 64,
                                  timeframe_ns=60, horizon_ns=300, available_ns=1)

if __name__ == "__main__":
    unittest.main()
