"""Inert wire-contract records only; no numerical worker, DB or engine launch."""
import copy
import unittest
from strattester.research.grid_math_history import digest
from strattester.research.history_scientific_handoff import handoff_packet

def review():
    p={'schema':'terminan.history.review.v1.1','result_receipt':'a'*64,
       'market':{'venue':'bybit','market_type':'linear','symbol':'BTCUSDT'},'strategy':'fixture',
       'model_version':'fixture-fixed','model':{'commit':'b'*40,'tree':'c'*40,'python_sha256':'d'*64,
           'manifest':{'python/worker.py':'e'*64}},
       'source':{'dataset_id':'1'*64,'snapshot_fingerprint':'2'*64,
          'identity':{'identity':'fixture','source_revision':'3'*40,'epoch':'fixture'},
          'units':{'price':'USDT/BTC','quantity':'BTC','cash':'USDT','time':'UTC_MS'},
          'source_authenticity':'REQUIRES_INDEPENDENT_RECEIPT_PROVISIONING'},
       'observations':[{'event_end_ms':60000,'available_at_ms':60500,'watermark_ms':60000,'close':101.0}],
       'math_trace':[{'feature_event_end_ms':60000,'feature_available_at_ms':60500,'decision_ms':61000,
           'forecast_target_event_end_ms':120000,'forecast':102.0,'request_digest':'4'*64}],
       'split_receipts':{'test':{'start_ms':30000,'end_ms':60000}},'oos_metrics':{'net_pnl':7.0},
       'evidence_class':'SYNTHETIC','execution_authority':False,'training_authorized':False,'trading_authorized':False}
    p['packet_fingerprint']=digest(p);return p

class DisplayHandoffContract(unittest.TestCase):
    def test_market_model_units_and_source_are_preserved(self):
        r=review();p=handoff_packet(r)
        self.assertEqual(p['market'],r['market'])
        for k in ('model','model_version','split_receipts'):self.assertEqual(p[k],r[k])
        self.assertEqual(p['units'],r['source']['units'])
        self.assertEqual(p['source'],r['source'])
        self.assertNotIn('oos_available_at_ms',p)  # absent publication is not guessed

    def test_explicit_publication_cannot_precede_evidence(self):
        p=handoff_packet(review(),published_at_ms=62000)
        self.assertEqual(p['oos_available_at_ms'],62000)
        self.assertEqual(p['published_at_ms'],62000)
        for t in (60000,60500,-1,True,2**53):
            with self.subTest(t=t),self.assertRaises(ValueError):handoff_packet(review(),published_at_ms=t)

    def test_existing_review_publication_is_preserved_and_cannot_be_overridden(self):
        r=review();r['published_at_ms']=62000;r['packet_fingerprint']=digest({k:v for k,v in r.items() if k!='packet_fingerprint'})
        self.assertEqual(handoff_packet(r)['published_at_ms'],62000)
        with self.assertRaises(ValueError):handoff_packet(r,published_at_ms=61000)

    def test_rehashed_invalid_market_units_and_safe_clock_fail(self):
        for mutate in (lambda r:r.update(market=r['source']['identity']),
                       lambda r:r['source']['units'].update(price='USD/BTC'),
                       lambda r:r['math_trace'][0].update(forecast_target_event_end_ms=2**53)):
            r=copy.deepcopy(review());mutate(r);r['packet_fingerprint']=digest({k:v for k,v in r.items() if k!='packet_fingerprint'})
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):handoff_packet(r)
