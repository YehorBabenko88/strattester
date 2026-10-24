"""Unit tests for the fail-closed structural report verifier (stdlib only)."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.cycle3_structural_report_gate import verify, REQUIRED_FILES, EXPECTED


class ReportGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"report.json"
        names=sorted(REQUIRED_FILES)
        nodes=[f"tests/research/{names[i % len(names)]}::test_case_{i}" for i in range(EXPECTED)]
        self.payload={"summary":{"passed":EXPECTED,"total":EXPECTED},
                      "tests":[{"nodeid":n,"outcome":"passed"} for n in nodes]}

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        self.path.write_text(json.dumps(self.payload),encoding="utf-8")
        verify(self.path)

    def test_valid(self):
        self.check()

    def test_duplicate_node_rejected(self):
        self.payload["tests"][1]["nodeid"]=self.payload["tests"][0]["nodeid"]
        with self.assertRaises(ValueError):self.check()

    def test_missing_required_file_rejected(self):
        for test in self.payload["tests"]:
            if test["nodeid"].split("/")[-1].startswith(sorted(REQUIRED_FILES)[-1]):
                test["nodeid"]=test["nodeid"].replace(sorted(REQUIRED_FILES)[-1],"unrequired.py")
        with self.assertRaises(ValueError):self.check()

    def test_skipped_rejected(self):
        self.payload["tests"][0]["outcome"]="skipped"
        with self.assertRaises(ValueError):self.check()

    def test_summary_mismatch_rejected(self):
        self.payload["summary"]["passed"]=EXPECTED-1
        with self.assertRaises(ValueError):self.check()


if __name__=="__main__":
    unittest.main()
