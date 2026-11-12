import copy
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.evaluation import fit, probabilities, metrics, split_at, run_evaluation, digest, block_permute, paired_block_interval, permute_edge_summaries


def sample(n=100):
    return [{'id':str(i),'cutoff':i*100,'label_end':i*100+220,'label_available':i*100+250,
             'label':('BREAKOUT','BOUNCE','TIMEOUT')[i%3],'group_id':str(i),
             'baseline':[float(i%3),float(i%7)],'graph':[float(i%3),float(i%7),float(i%5)]} for i in range(n)]


class Checks(unittest.TestCase):
    def test_probability_normalized_finite(self):
        rows=sample();m=fit(rows,'baseline')
        p=probabilities(m,[2,3])
        self.assertAlmostEqual(sum(p),1)
        self.assertTrue(all(math.isfinite(v) and 0<v<1 for v in p))

    def test_purge_maturity_embargo(self):
        rows=sample();s=split_at(rows,4000,6000,8000,100)
        self.assertTrue(all(max(r['label_end'],r['label_available'])+100<4000 for r in s['train']))
        self.assertTrue(all(max(r['label_end'],r['label_available'])+100<6000 for r in s['calibration']))
        self.assertGreater(s['excluded']['train'],0)

    def test_cross_split_group_rejected(self):
        rows=sample();rows[60]['group_id']=rows[1]['group_id']
        with self.assertRaises(ValueError):split_at(rows,4000,6000,8000,100)

    def test_test_values_cannot_change_fit(self):
        rows=sample();before=run_evaluation(rows,embargo=100)
        mutated=copy.deepcopy(rows)
        for r in mutated:
            if r['cutoff']>=before['final']['test_start']:
                r['label']='TIMEOUT';r['baseline']=[999,888];r['graph']=[999,888,777]
        after=run_evaluation(mutated,embargo=100)
        self.assertEqual(before['final']['models'],after['final']['models'])

    def test_metrics_guard_shape_and_probability(self):
        with self.assertRaises(ValueError):metrics(['BREAKOUT'],[])
        with self.assertRaises(ValueError):metrics(['BREAKOUT'],[[float('nan'),0,1]])

    def test_train_only_scaler(self):
        m=fit(sample(20),'baseline')
        self.assertEqual(m['mean'][0],sum(i%3 for i in range(20))/20)

    def test_block_control_preserves_label_counts(self):
        rows=sample(31);control=block_permute(rows)
        self.assertEqual(sorted(r['label'] for r in rows),sorted(r['label'] for r in control))
        self.assertNotEqual([r['label'] for r in rows],[r['label'] for r in control])

    def test_reproducible_full_report(self):
        self.assertEqual(digest(run_evaluation(sample(),100)),digest(run_evaluation(sample(),100)))

    def test_paired_block_uncertainty_preserves_constant_difference(self):
        result=paired_block_interval([.2]*20,block=4)
        self.assertAlmostEqual(result['lower'],.2)
        self.assertAlmostEqual(result['upper'],.2)

    def test_periodic_control_is_not_identity(self):
        rows=sample(27)
        self.assertNotEqual([r['label'] for r in rows],[r['label'] for r in block_permute(rows)])

    def test_uninformative_constant_control_rejected(self):
        rows=sample(12)
        for r in rows:r['label']='BOUNCE'
        with self.assertRaisesRegex(ValueError,'CONTROL_UNINFORMATIVE'):block_permute(rows)

    def test_edge_control_preserves_node_summaries(self):
        rows=sample(20)
        for i,r in enumerate(rows):r['graph']=r['baseline']+[i,i+1,i+2,i+3,i+4]
        changed=permute_edge_summaries(rows)
        for a,b in zip(rows,changed):
            self.assertEqual(a['graph'][:4]+a['graph'][-1:],b['graph'][:4]+b['graph'][-1:])
        self.assertNotEqual([r['graph'][4:6] for r in rows],[r['graph'][4:6] for r in changed])

    def test_evaluation_asof_excludes_unmatured_labels(self):
        s=split_at(sample(),4000,6000,8000,100,evaluation_as_of=7000)
        self.assertTrue(all(r['label_available']<=7000 for r in s['test']))


if __name__=='__main__':unittest.main(verbosity=2)
