"""Literal, unqualified contract fixtures. No Math implementation is executed."""
import copy
import unittest
from tests.research.test_display_handoff_contract import review
from strattester.research.grid_math_history import digest
from strattester.research.history_scientific_handoff import handoff_packet

def inputs():
    r=review();row={'event_start_ms':0,'event_end_ms':60000,'source_event_start_ms':1,'source_event_end_ms':59999,
        'available_at_ms':60500,'watermark_ms':60000,'close':101,'revision':'5'*64,'source_receipt_hash':'6'*64}
    h={'dataset_id':r['source']['dataset_id'],'dataset_fingerprint':r['source']['snapshot_fingerprint'],
       'source':r['source']['identity'],'market':r['market'],'units':{'price':'USDT/BTC','volume':'BTC'},
       'decision_ms':61000,'rows':[row]}
    q={'schema':'math.history.scientific.request.v1','history':h,'graph':{'nodes':[],'edges':[],'outputs':[]}}
    r['math_trace'][0]['request_digest']=digest(h)
    r['packet_fingerprint']=digest({k:v for k,v in r.items() if k!='packet_fingerprint'})
    packet=handoff_packet(r,published_at_ms=62000)
    model={**r['model'],'node_sha256':'7'*64,'manifest':{**r['model']['manifest'],'src/engine.mjs':'8'*64}}
    result={'schema':'math.history.scientific.result.v1','api_revision':'history-1.1+scientific-2.1',
        'provenance':h,'request_digest':digest(q),'history':{'request_digest':digest(h),'prefix_digest':digest(h['rows']),
            'decision_ms':61000,'feature_event_end_ms':60000,'feature_available_at_ms':60500,
            'forecast_target_event_end_ms':120000,'forecast':102.0},
        'scientific':{'schema':'math.scientific.result.v2','status':'RESEARCH_ONLY'},'math_source':model,
        'execution_authority':False,'training_authorized':False,'trading_authorized':False}
    result['completion_receipt']=digest(result)
    return packet,q,result

class JointDisplayContract(unittest.TestCase):
    def test_forecast_feature_clocks_are_bound_to_joint_result(self):
        from strattester.research.history_joint_display import joint_display_packet
        p,q,r=inputs();p['forecast_points'][0]['feature_available_at_ms']=60000
        p['handoff_sha256']=digest({k:v for k,v in p.items() if k!='handoff_sha256'})
        with self.assertRaises(ValueError):joint_display_packet(p,q,r,r['completion_receipt'],joint_published_at_ms=61500)

    def test_export_preserves_original_records_and_stays_unqualified(self):
        from strattester.research.history_joint_display import joint_display_packet
        p,q,r=inputs();out=joint_display_packet(p,q,r,r['completion_receipt'],joint_published_at_ms=61500)
        self.assertEqual(out['schema'],'terminan.unified-display.v1')
        self.assertEqual(out['joint_result'],r);self.assertEqual(out['joint_request'],q)
        self.assertEqual(out['history'],p);self.assertTrue(out['contract_only'])
        self.assertEqual(out['qualification'],'NOT_QUALIFIED')

    def test_tampered_request_source_receipt_and_publication_fail(self):
        from strattester.research.history_joint_display import joint_display_packet
        for mutation in ('receipt','request','source','clock'):
            p,q,r=copy.deepcopy(inputs());pin=r['completion_receipt'];t=61500
            if mutation=='receipt':pin='0'*64
            if mutation=='request':q['history']['rows'][0]['close']=999
            if mutation=='source':r['math_source']['commit']='0'*40;r['completion_receipt']=digest({k:v for k,v in r.items() if k!='completion_receipt'});pin=r['completion_receipt']
            if mutation=='clock':t=60000
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):joint_display_packet(p,q,r,pin,joint_published_at_ms=t)
