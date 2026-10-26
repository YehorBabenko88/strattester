"""Portable build input tests and safe native diagnostics/refusal tests.

NATIVE_BROKER selects a compiled broker. These tests NEVER enable VM selftests.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_build', ROOT / 'scripts/build_windows_native.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class PinnedInputTests(unittest.TestCase):
    def test_corrupt_package_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'input.zip'
            archive.write_bytes(b'not an executable package')
            output = Path(temp) / 'out'
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                build.extract_verified(archive, '0' * 64, output)
            self.assertFalse(output.exists())

    def test_hash_correct_archive_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'input.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('../escaped', 'bad')
            output = Path(temp) / 'out'
            with self.assertRaisesRegex(ValueError, 'unsafe package member'):
                build.extract_verified(archive, hashlib.sha256(archive.read_bytes()).hexdigest(), output)
            self.assertFalse((Path(temp) / 'escaped').exists())

@unittest.skipUnless(os.name == 'nt' and os.environ.get('NATIVE_BROKER'), 'set NATIVE_BROKER for safe compiled CLI tests')
class NativeCliTests(unittest.TestCase):
    def invoke(self, *args):
        env = dict(os.environ)
        # Never run the native component APIs on the active physical host.
        for name in ('GITHUB_ACTIONS', 'RUNNER_ENVIRONMENT', 'RUNNER_OS'):
            env.pop(name, None)
        result = subprocess.run([os.environ['NATIVE_BROKER'], *args], text=True,
                                capture_output=True, timeout=10, env=env)
        return result.returncode, json.loads(result.stdout)

    def test_diagnostic_binds_actual_binary_and_stays_blocked(self):
        code, data = self.invoke('--diagnose')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'BLOCKED')
        self.assertFalse(data['native_enforcement'])
        self.assertFalse(data['research_process_created'])
        self.assertEqual(data['component_validation'], 'NOTRUN')
        self.assertEqual(data['binary_sha256'], hashlib.sha256(Path(os.environ['NATIVE_BROKER']).read_bytes()).hexdigest())

    def test_launch_does_not_execute_arbitrary_command(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'MUST_NOT_EXIST'
            code, data = self.invoke('--launch', 'cmd.exe', '/c', 'echo', 'unsafe', '>', str(marker))
            self.assertEqual(code, 78)
            self.assertEqual(data['reason'], 'MANDATORY_CONTROLS_NOT_IMPLEMENTED')
            self.assertFalse(data['research_process_created'])
            self.assertFalse(marker.exists())

    def test_selftest_is_refused_without_disposable_vm_guard(self):
        code, data = self.invoke('--selftest-native', 'COMPONENT_TESTS_ONLY')
        self.assertEqual(code, 78)
        self.assertEqual(data['reason'], 'DISPOSABLE_HOSTED_VM_REQUIRED')
        self.assertFalse(data['research_process_created'])

    def test_diagnose_rejects_extra_arguments(self):
        code, data = self.invoke('--diagnose', '--launch')
        self.assertEqual(code, 64)
        self.assertFalse(data['research_process_created'])

if __name__ == '__main__':
    unittest.main()
