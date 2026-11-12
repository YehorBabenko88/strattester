from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.run import run_research


class Checks(unittest.TestCase):
    def test_replay_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as scratch:
            a=run_research(Path(scratch)/'a','a'*40,n=6000)
            b=run_research(Path(scratch)/'b','a'*40,n=6000)
            self.assertEqual(a['reproducible_sha256'],b['reproducible_sha256'])
            self.assertTrue((Path(scratch)/'a'/'checkpoint.json').is_file())
            self.assertEqual(a['status'],'MWI_OFFLINE_RESEARCH_READY')

    def test_input_snapshot_reuses_pinned_bytes(self):
        with tempfile.TemporaryDirectory() as scratch:
            a=run_research(Path(scratch)/'a','a'*40,n=6000)
            b=run_research(Path(scratch)/'b','a'*40,snapshot=Path(scratch)/'a'/'dataset',pin=a['dataset']['manifest_sha256'])
            self.assertEqual(a['evaluation'],b['evaluation'])


if __name__=='__main__':unittest.main(verbosity=2)
