import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.strategy import candidates
from mwi_offline.unified_adapter import prepare_unified

class Checks(unittest.TestCase):
    def setUp(self):self.c=candidates('a'*64,'b'*64)[2]
    def test_preparation_never_assigns_authority_or_owner_ids(self):
        r=prepare_unified(self.c)
        self.assertEqual(r['owner_operation'],'prepare_research_plan')
        self.assertEqual(r['status'],'PREPARATION_BLOCKED')
        for key in ('submitted','authenticated','effects_authorized','public_submit','source_admitted'):
            self.assertIs(r[key],False)
        for key in ('endpoint','job_id','experiment_id','lease','fencing_token','owner_plan'):
            self.assertIsNone(r[key])
        self.assertEqual(r['source_context'],'UNKNOWN')
        self.assertEqual(r['public_submit_policy'],'DENY')
    def test_candidate_id_not_truncated_to_source_sha(self):
        r=prepare_unified(self.c)
        self.assertIsNone(r['strategy_source_sha'])
        self.assertEqual(r['local_candidate_id'],self.c['strategy_id'])
        with self.assertRaises(ValueError):prepare_unified(self.c,strategy_source_sha=self.c['strategy_id'])
    def test_supplied_source_is_only_context_and_synthetic_funding_blocked(self):
        r=prepare_unified(self.c,strategy_source_sha='c'*40)
        self.assertEqual(r['strategy_source_sha'],'c'*40)
        self.assertFalse(r['source_admitted'])
        self.assertIn('SOURCE_SIGNED_FUNDING_UNAVAILABLE',r['blockers'])
        self.assertIn('MATH_OWNER_CONFIGURATION_UNAVAILABLE',r['blockers'])
        self.assertEqual(r['funding'],'SYNTHETIC_ZERO_ASSUMPTION')
        self.assertEqual(r['requested_mode'],'SIMULATION_ONLY')
    def test_deterministic_no_mutation_and_hash_binding(self):
        old=copy.deepcopy(self.c);a=prepare_unified(self.c);b=prepare_unified(self.c)
        self.assertEqual(a,b);self.assertEqual(old,self.c)
        other=prepare_unified(candidates('d'*64,'b'*64)[2])
        self.assertNotEqual(a['preparation_sha256'],other['preparation_sha256'])
    def test_closed_candidate_and_hostile_objects_rejected(self):
        for value in (dict(self.c,authenticated=True),dict(self.c,threshold=float('nan')),object()):
            with self.assertRaises(ValueError):prepare_unified(value)
        class Hostile(dict):
            def items(self):raise AssertionError('callback')
        with self.assertRaises(ValueError):prepare_unified(Hostile(self.c))

if __name__=='__main__':unittest.main(verbosity=2)
