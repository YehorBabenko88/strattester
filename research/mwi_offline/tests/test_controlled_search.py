from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mwi_offline.controlled_search import prepare_search
from mwi_offline.strategy import candidates, next_version


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.cs = candidates('a'*64, 'b'*64)

    def test_semantic_duplicate_retained_and_wait_valid(self):
        result = prepare_search([self.cs[0], next_version(self.cs[0], .7), self.cs[1]], 3)
        self.assertEqual([x['status'] for x in result['records']], ['ACCEPTED', 'DUPLICATE', 'ACCEPTED'])
        self.assertEqual(len(result['candidates']), 2)
        self.assertFalse(result['promotion_allowed'])

    def test_fixed_budget_retains_refusals(self):
        result = prepare_search(self.cs, 2)
        self.assertEqual(len(result['records']), 6)
        self.assertEqual([x['status'] for x in result['records'][2:]], ['BUDGET_REFUSED']*4)

    def test_invalid_risk_retained(self):
        bad = dict(self.cs[0]); bad['position_usd'] = 10000
        result = prepare_search([bad, self.cs[0]], 2)
        self.assertEqual(result['records'][0]['status'], 'VALIDATION_REFUSED')
        self.assertEqual(result['records'][1]['status'], 'ACCEPTED')

    def test_identity_and_model_lineage_preserved(self):
        other = candidates('a'*64, 'c'*64)[0]
        self.assertEqual(len(prepare_search([self.cs[0], other], 2)['candidates']), 2)

    def test_deterministic_no_input_mutation(self):
        import copy
        before = copy.deepcopy(self.cs)
        self.assertEqual(prepare_search(self.cs, 6), prepare_search(self.cs, 6))
        self.assertEqual(self.cs, before)

    def test_bounded_plain_inputs(self):
        for values, budget in ((self.cs, True), (self.cs, 7), (self.cs*2, 6), (iter(self.cs), 6)):
            with self.assertRaises(ValueError): prepare_search(values, budget)

    def test_noncanonical_numbers_rejected_before_result_hashing(self):
        for value, reason in ((float('nan'), 'FINITE_DECLARATION'), (2**54, 'INTEGER_DECLARATION')):
            bad = dict(self.cs[0]); bad['position_usd'] = value
            with self.assertRaisesRegex(ValueError, reason): prepare_search([bad], 1)

    def test_shared_subtree_work_amplification_is_bounded(self):
        value = 0
        for _ in range(5): value = [value]*16
        with self.assertRaisesRegex(ValueError, 'DECLARATION_WORK_BUDGET'):
            prepare_search([{'invalid':value}], 1)


if __name__ == '__main__': unittest.main()
