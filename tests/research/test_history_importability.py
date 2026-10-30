"""The handoff must be importable before it can enforce source admission."""
import pathlib
import unittest


class HandoffImportability(unittest.TestCase):
    def test_handoff_and_its_regression_suite_compile(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ('strattester/research/history_scientific_handoff.py',
                     'tests/research/test_history_scientific_handoff.py'):
            with self.subTest(path=name):
                try:
                    compile((root / name).read_bytes(), name, 'exec')
                except SyntaxError as exc:
                    self.fail(f'{name} is not executable Python: {exc}')
