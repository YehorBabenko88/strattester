from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.strategy import candidates, validate, propose, next_version

class Checks(unittest.TestCase):
    def setUp(self):self.cs=candidates('a'*64,'b'*64)
    def test_candidates_have_immutable_lineage_and_no_promotion(self):
        self.assertEqual(len(self.cs),6)
        for c in self.cs:
            validate(c);self.assertFalse(c['promotion_allowed']);self.assertEqual(c['mode'],'SIMULATION_ONLY')
    def test_code_unknown_and_live_refused(self):
        for change in ({'code':'exec(x)'},{'mode':'LIVE'},{'entry':{'eval':'x'}},{'promotion_allowed':True}):
            c=dict(self.cs[0]);c.update(change)
            with self.assertRaises(ValueError):validate(c)
    def test_risk_and_resource_caps(self):
        for key,value in (('position_usd',101),('max_drawdown',.9),('threshold',.1),('horizon',999),('version',True)):
            c=dict(self.cs[0]);c[key]=value
            with self.assertRaises(ValueError):validate(c)
    def test_strategy_fingerprint_covers_parameters(self):
        c=dict(self.cs[0]);c['threshold']=.75
        with self.assertRaises(ValueError):validate(c)
    def test_future_labels_cannot_change_decision(self):
        e={'baseline':[1,0,0,0,1,1,1,1],'label':'BREAKOUT'}
        before=propose(self.cs[2],e,[.9,.05,.05]);e['label']='BOUNCE'
        self.assertEqual(before,propose(self.cs[2],e,[.9,.05,.05]))
    def test_support_reverses_direction(self):
        self.assertEqual(propose(self.cs[2],{'baseline':[-1]*8},[.9,.05,.05])['side'],'short')
    def test_timeout_low_confidence_wait(self):
        for p in ([.2,.2,.6],[.4,.3,.3]):self.assertEqual(propose(self.cs[2],{'baseline':[1]*8},p)['action'],'WAIT')
    def test_invalid_probability_refused(self):
        for p in ([.8,.8,.1],[float('nan'),0,1],[1,0]):
            with self.assertRaises(ValueError):propose(self.cs[2],{'baseline':[1]*8},p)
    def test_next_version_changes_lineage_not_parent(self):
        old=dict(self.cs[0]);new=next_version(old,.7)
        self.assertEqual(old,self.cs[0]);self.assertEqual(new['parent_id'],old['strategy_id'])
        self.assertNotEqual(new['strategy_id'],old['strategy_id']);validate(new)

if __name__=='__main__':unittest.main(verbosity=2)
