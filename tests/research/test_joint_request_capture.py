"""Transport capture test: actual admission, inert worker reply, no Math launch."""
import copy
import json
from pathlib import Path
import unittest
from strattester.research.grid_math_history import digest
from strattester.research.history_joint import JointMathClient

class JointRequestCapture(unittest.TestCase):
    def test_original_request_survives_composition_for_later_display_export(self):
        source=json.loads((Path(__file__).parents[1]/'fixtures/history-replay-contract.v1.json').read_bytes())
        dataset={'schema':'grid.history.v1.1','request':source['source_request'],'source':source['source'],
            'evidence_class':source['evidence_class'],'rows':source['observations'],'source_receipts':source['source_receipts'],
            'execution_authority':False,'trading_authorized':False,'watermark_ms':source['watermark_ms'],
            'dataset_id':source['dataset_id'],'dataset_fingerprint':source['dataset_fingerprint']}
        client=object.__new__(JointMathClient)
        client.commit='b'*40;client.tree='c'*40;client.python_sha256='d'*64;client.node_sha256='e'*64;client.joint_manifest={};client.node='INERT_NOT_EXECUTED'
        client._node_pin=lambda:None
        def inert(q,*args):
            h=q['history']
            return {'schema':'math.history.scientific.result.v1','request_digest':digest(q),
                'api_revision':'history-1.1+scientific-2.1',
                'provenance':{k:h[k] for k in ('dataset_id','dataset_fingerprint','source','market','units','decision_ms','rows')},
                'history':{'prefix_digest':digest(h['rows'])},'scientific':{'schema':'math.scientific.result.v2'},
                'execution_authority':False,'training_authorized':False,'trading_authorized':False}
        client._execute=inert
        graph={'nodes':[{'id':'twice','kind':'formula','expression':'x*2','outputUnit':'USDT/BTC'}],
            'edges':[{'from':{'node':'history','port':'value'},'to':{'node':'twice','port':'x'}}],
            'outputs':[{'node':'twice','port':'value'}]}
        result=client.compose(dataset,dataset['dataset_fingerprint'],2400000,30,1800000,graph)
        self.assertEqual(digest(result['joint_request']),result['request_digest'])
        self.assertEqual(result['joint_request']['graph'],graph)
        graph['nodes'][0]['expression']='altered'
        self.assertEqual(result['joint_request']['graph']['nodes'][0]['expression'],'x*2')
        result['math_source']['manifest']['changed']='f'*64
        self.assertEqual(client.joint_manifest,{})
