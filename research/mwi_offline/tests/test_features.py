import copy
import math
import unittest
from mwi_offline.synthetic import generate
from mwi_offline.features import build_examples


def fixture(side=1, kind="BREAKOUT", horizon=12):
    bars=[]
    for i in range(48):
        bars.append(dict(symbol="TOYUSDT",open_ms=i*60000,end_ms=(i+1)*60000,available_ms=(i+1)*60000,open=100.,high=102.,low=98.,close=100.,volume=10.))
    c=101.95 if side==1 else 98.05
    bars.append(dict(symbol="TOYUSDT",open_ms=48*60000,end_ms=49*60000,available_ms=49*60000,open=100.,high=max(100.,c)+.05,low=min(100.,c)-.05,close=c,volume=10.))
    for j in range(horizon):
        high,low=(110.,90.) if kind=="AMBIGUOUS" and j==0 else ((102.2,101.8) if side==1 else (98.2,97.8))
        if kind=="BREAKOUT" and j==0:
            high,low=(110.,101.) if side==1 else (99.,90.)
        if kind=="BOUNCE" and j==0:
            high,low=(103.,90.) if side==1 else (110.,97.)
        bars.append(dict(symbol="TOYUSDT",open_ms=(49+j)*60000,end_ms=(50+j)*60000,available_ms=(50+j)*60000,open=(high+low)/2,high=high,low=low,close=(high+low)/2,volume=10.))
    return bars


class FeatureChecks(unittest.TestCase):
    def test_continuous_deterministic_synthetic(self):
        a=generate(); self.assertEqual(a,generate());self.assertEqual(len(a),1800)
        for left,right in zip(a,a[1:]):
            self.assertEqual(left["close"],right["open"])
            self.assertEqual(left["end_ms"],right["open_ms"])

    def test_enough_nonoverlapping_equal_cohort(self):
        result=build_examples(generate()); rows=result["examples"]
        self.assertGreaterEqual(len(rows),60);self.assertLessEqual(len(rows),256)
        self.assertTrue(all(result["counts"][label]>0 for label in ("BREAKOUT","BOUNCE","TIMEOUT")))
        sizes=result["feature_names"]
        for r in rows:
            self.assertEqual(len(r["baseline"]),len(sizes["baseline"]))
            self.assertEqual(len(r["graph"]),len(sizes["graph"]))
            self.assertEqual(r["baseline"],r["graph"][:len(r["baseline"])])
            self.assertEqual(r["node_only"],r["baseline"]+r["graph"][len(r["baseline"]):len(r["baseline"])+2]+r["graph"][-1:])
            self.assertTrue(all(math.isfinite(x) for x in r["graph"]))
            self.assertLess(r["cutoff"],r["label_end"])
            self.assertGreaterEqual(r["label_available"],r["label_end"])
        for a,b in zip(rows,rows[1:]):self.assertLess(a["label_end"],b["cutoff"])

    def test_full_run_class_support(self):
        from collections import Counter
        rows=build_examples(generate(n=6000))["examples"]
        self.assertLessEqual(len(rows),256)
        counts=Counter(r["label"] for r in rows)
        final=Counter(r["label"] for r in rows[int(len(rows)*.8):])
        for label in ("BREAKOUT","BOUNCE","TIMEOUT"):
            self.assertGreaterEqual(counts[label],10)
            self.assertGreaterEqual(final[label],2)

    def test_orientation_both_support_and_resistance(self):
        for side in (-1,1):
            for kind in ("BREAKOUT","BOUNCE"):
                first=build_examples(fixture(side,kind))["examples"][0]
                self.assertEqual(first["label"],kind)
                self.assertEqual(first["baseline"][0],side)

    def test_timeout_ambiguous_pending_and_unobservable(self):
        for kind in ("TIMEOUT","AMBIGUOUS"):
            out=build_examples(fixture(kind=kind))
            if kind=="TIMEOUT":self.assertEqual(out["examples"][0]["label"],kind)
            else:self.assertEqual(out["counts"][kind],1)
        self.assertEqual(build_examples(fixture()[:-1])["counts"]["PENDING"],1)
        bars=fixture(); del bars[50]
        self.assertEqual(build_examples(bars)["counts"]["UNOBSERVABLE"],1)

    def test_future_raw_mutation_cannot_change_snapshot(self):
        a=fixture();b=copy.deepcopy(a)
        b[49].update(open=100.,close=100.,high=103.,low=90.)
        x=build_examples(a)["examples"][0];y=build_examples(b)["examples"][0]
        self.assertNotEqual(x["label"],y["label"])
        self.assertEqual(x["state_hash"],y["state_hash"])
        self.assertEqual(x["graph"],y["graph"])

    def test_late_prior_bar_is_not_used(self):
        bars=fixture();bars[47]["available_ms"]+=60000
        self.assertFalse(build_examples(bars)["examples"])

    def test_label_maturity_preserves_delayed_availability(self):
        bars=fixture();bars[-1]["available_ms"]+=120000
        row=build_examples(bars)["examples"][0]
        self.assertEqual(row["label_available"],bars[-1]["available_ms"])

    def test_invalid_observations_refused(self):
        for field,value in (("close",float("nan")),("available_ms",None),("available_ms",0)):
            bars=fixture();bars[3][field]=value
            with self.assertRaises(ValueError):build_examples(bars)

    def test_input_not_mutated(self):
        a=fixture();before=copy.deepcopy(a);build_examples(a);self.assertEqual(a,before)


if __name__=="__main__":unittest.main()
