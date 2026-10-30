import copy
import importlib.util
from pathlib import Path
import unittest

from strattester.research.grid_math_history import replay, digest
from strattester.research.history_terminan import review_packet
from strattester.research.history_scientific_handoff import handoff_packet

fixture_path = Path(__file__).with_name("test_grid_math_history_v11.py")
spec = importlib.util.spec_from_file_location("handoff_fixture", fixture_path)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = fixtures.dataset()
        with fixtures.client() as client:
            result = replay(d, d["dataset_fingerprint"], client, fixtures.policy())
        cls.review = review_packet(result, result["completion_receipt"])

    def test_bounded_readonly_handoff(self):
        p = handoff_packet(self.review)
        self.assertEqual(p["schema"], "terminan.history.scientific-handoff.v1")
        self.assertEqual(p["scientific_api"], "NOT_EXECUTED")
        self.assertEqual(p["source_authenticity"], "UNATTESTED")
        self.assertFalse(p["execution_authority"])
        self.assertEqual(p["observed_prices"][0]["event_end_ms"],
                         self.review["observations"][0]["event_end_ms"])
        self.assertEqual(p["observed_prices"][0]["available_at_ms"],
                         self.review["observations"][0]["available_at_ms"])
        self.assertEqual(p["handoff_sha256"], digest({k:v for k,v in p.items()
                                                     if k != "handoff_sha256"}))
        self.assertTrue(p["forecast_points"])
        self.assertEqual(p["market"], self.review["source"]["identity"])
        self.assertEqual(p["strategy"], self.review["strategy"])

    def test_mutations_fail_closed(self):
        for change in (
            lambda p: p.update(packet_fingerprint="0"*64),
            lambda p: p.update(trading_authorized=True),
            lambda p: p["observations"][0].update(available_at_ms=0),
            lambda p: p["observations"][0].update(close=float("nan")),
            lambda p: p.update(evidence_class="HISTORICAL"),
            lambda p: p["math_trace"][0].update(forecast=-1),
            lambda p: p["math_trace"][0].update(request_digest="not-a-digest"),
        ):
            r = copy.deepcopy(self.review)
            change(r)
            with self.subTest(change=change), self.assertRaises(ValueError):
                handoff_packet(r)

    def test_export_preserves_model_units_splits_and_oos_clock(self):
        p = handoff_packet(self.review)
        self.assertEqual(p['model'], self.review['model'])
        self.assertEqual(p['model_version'], 'grid-frozen-analog-v1')
        self.assertEqual(p['units']['price'], 'USDT/BTC')
        self.assertEqual(p['split_receipts'], self.review['split_receipts'])
        self.assertEqual(p['oos_available_at_ms'], 4800000)
        self.assertGreater(len(p['forecast_points']), 2)

    def test_rehashed_clock_and_units_mutations_still_fail(self):
        for mutate in (
            lambda r: r['math_trace'][0].update(forecast_target_event_end_ms=2**53),
            lambda r: r['source']['units'].update(price='USD/BTC'),
            lambda r: r['math_trace'][0].update(request_digest='not-a-digest'),
        ):
            r = copy.deepcopy(self.review)
            mutate(r)
            r['packet_fingerprint'] = digest({k:v for k,v in r.items() if k!='packet_fingerprint'})
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                handoff_packet(r)


if __name__ == "__main__":
    unittest.main()
