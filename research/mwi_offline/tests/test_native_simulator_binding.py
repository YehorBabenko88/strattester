import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mwi_offline.simulation_adapter import materialize_binding,bind_existing,inspect_binding

class Checks(unittest.TestCase):
    def test_exact_git_bytes_bind_in_fresh_namespace_and_preserve_source(self):
        repo=Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'capsule';materialize_binding(repo,root)
            before=inspect_binding(root);binding=bind_existing(root)
            signal=binding['Signal'](0,'long','market',None,99.,101.)
            policy=binding['ExecutionPolicy'](60000,.00055,2.,'SL_FIRST',100.)
            result=binding['simulate_trade'](signal,[{'t':0,'open':100.,'high':102.,'low':98.,'close':100.}],policy,metadata={'scope':'SYNTHETIC'})
            self.assertEqual(result.exit_reason,'SL');self.assertLess(result.net_pnl,0)
            self.assertEqual(before,inspect_binding(root))
            self.assertNotIn('strattester.research.execution',sys.modules)
    def test_crlf_normalization_is_not_source_admission(self):
        repo=Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'capsule';materialize_binding(repo,root)
            p=root/'strattester/research/execution.py';raw=p.read_bytes()
            self.assertNotIn(b'\r\n',raw);p.write_bytes(raw.replace(b'\n',b'\r\n'))
            with self.assertRaisesRegex(ValueError,'RAW_SOURCE_PIN'):bind_existing(root)
    def test_callbacks_bad_metadata_and_unfilled_entry_refused(self):
        repo=Path(__file__).resolve().parents[3]
        class Hostile:
            def __iter__(self):raise AssertionError('CALLBACK_EXECUTED')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'capsule';materialize_binding(repo,root);b=bind_existing(root)
            signal=b['Signal'](0,'long','market',None,99.,101.);policy=b['ExecutionPolicy'](60000,.00055,2.,'SL_FIRST',100.)
            rows=[{'t':0,'open':100.,'high':100.1,'low':99.9,'close':100.}]
            for value in (Hostile(),{'x':Hostile()},{'x':float('nan')}):
                with self.assertRaises(ValueError):b['simulate_trade'](signal,rows,policy,metadata=value)
            with self.assertRaises(ValueError):b['simulate_trade'](signal,Hostile(),policy)
            signal=b['Signal'](0,'long','limit',98.,97.,101.)
            with self.assertRaisesRegex(ValueError,'ENTRY_NOT_FILLED'):b['simulate_trade'](signal,rows,policy)

if __name__=='__main__':unittest.main(verbosity=2)
