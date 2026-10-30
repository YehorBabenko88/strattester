import copy
import importlib.util
import os
from pathlib import Path
import sys
import unittest

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('timed_fixture',here/'test_grid_math_history_v11.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
from strattester.research.grid_math_history import replay, digest
from strattester.research.history_terminan import review_packet, render_review


class Review(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=fixtures.dataset()
        with fixtures.client() as c:cls.result=replay(d,d['dataset_fingerprint'],c,fixtures.policy())

    def test_readonly_packet_and_escaped_display(self):
        r=self.result;p=review_packet(r,r['completion_receipt'])
        self.assertEqual(p['schema'],'terminan.history.review.v1.1')
        self.assertFalse(p['training_authorized']);self.assertFalse(p['trading_authorized'])
        self.assertEqual(p['oos_metrics'],r['splits']['test']['metrics'])
        self.assertEqual(p['source']['dataset_id'],r['dataset_id'])
        self.assertTrue(all(x['side'] in ('long','short') for x in p['trade_events']))
        h=render_review(r,r['completion_receipt'])
        self.assertIn('SYNTHETIC',h);self.assertIn('<svg',h)
        self.assertNotIn('<script',h);self.assertNotIn('fetch(',h)
        injected=copy.deepcopy(r);injected['warnings'].append('<img src=x onerror=alert(1)>')
        injected['completion_receipt']=digest({k:v for k,v in injected.items() if k!='completion_receipt'})
        self.assertNotIn('<img',render_review(injected,injected['completion_receipt']))
        if os.environ.get('HISTORY_EVIDENCE_ROOT'):
            out=Path(os.environ['HISTORY_EVIDENCE_ROOT']);out.mkdir(parents=True,exist_ok=True)
            (out/'terminan-review.html').write_text(h,encoding='utf8')
            import json
            (out/'terminan-review-packet.json').write_text(json.dumps(p,indent=2,sort_keys=True),encoding='utf8')

    def test_receipt_tamper_future_label_and_authority_denied(self):
        r=self.result
        with self.assertRaises(ValueError):review_packet(r,'0'*64)
        for mutation in (lambda r:r.update(training_authorized=True),
                         lambda r:r['training_candidates'][0].update(origin_ms=999999999),
                         lambda r:r['training_candidates'][0].update(label_close=999),
                         lambda r:r['splits']['test']['metrics'].update(net_pnl=999),
                         lambda r:r['market'].update(symbol='ETHUSDT'),
                         lambda r:r['units'].update(cash='BTC'),
                         lambda r:r['math_trace'][-1].update(train_count=80),
                         lambda r:r['math_trace'][-1].update(request_digest='forged')):
            r=copy.deepcopy(self.result);mutation(r)
            r['completion_receipt']=digest({k:v for k,v in r.items() if k!='completion_receipt'})
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):review_packet(r,r['completion_receipt'])

    def test_actual_terminan_trade_parser_compatibility(self):
        root=Path(os.environ.get('TERMINAN_REFERENCE',fixtures.ROOT.parent/'terminan-reference'))
        if not (root/'terminan/contracts.py').is_file():
            if os.environ.get('HISTORY_REQUIRE_CROSSREPO')=='1':self.fail('Terminan fixture pin required')
            self.skipTest('Terminan reference not provisioned')
        spec=importlib.util.spec_from_file_location('terminan_contract_reference',root/'terminan/contracts.py')
        mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
        packet=review_packet(self.result,self.result['completion_receipt'])
        self.assertTrue(packet['trade_events'])
        for trade in packet['trade_events']:mod.TradeEvent.parse(trade)

if __name__=='__main__':unittest.main()
