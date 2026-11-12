from pathlib import Path
import sys
import subprocess
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_engine_guarded import guarded

class Checks(unittest.TestCase):
    def test_only_fixed_isolated_child_with_timeout(self):
        with patch('run_engine_guarded.subprocess.run') as run:
            run.return_value.returncode=0
            self.assertEqual(guarded(['--output','new','--source-head','a'*40]),0)
            args,kwargs=run.call_args
            self.assertEqual(args[0][:4],[sys.executable,'-I','-S','-B'])
            self.assertTrue(args[0][4].endswith('run_engine_cycle.py'))
            self.assertEqual(kwargs,{'timeout':60,'check':False})
    def test_timeout_reports_stopped_child(self):
        with patch('run_engine_guarded.subprocess.run',side_effect=subprocess.TimeoutExpired('fixed-child',60)):
            self.assertEqual(guarded([]),124)

if __name__=='__main__':unittest.main(verbosity=2)
