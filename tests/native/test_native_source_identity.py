import importlib.util,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('owner_build',ROOT/'scripts/build_windows_native.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
class SourceIdentityTests(unittest.TestCase):
 def fixture(self,root):
  (root/'native/windows').mkdir(parents=True);(root/'scripts').mkdir()
  (root/'native/windows/Broker.cs').write_bytes(b'committed source\n');(root/'scripts/build_windows_native.py').write_bytes(b'committed builder\n')
  def git(*a):return subprocess.run(['git','-C',str(root),*a],capture_output=True,check=True,text=True).stdout.strip()
  git('init');git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture')
  return git
 def test_clean_source_snapshot_is_exact_git_object_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);self.fixture(r);identity,files=build.source_snapshot(r)
   self.assertFalse(identity['dirty']);self.assertEqual(files['native/windows/Broker.cs'],b'committed source\n')
 def test_skip_worktree_modification_cannot_claim_clean_source(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);git=self.fixture(r);git('update-index','--skip-worktree','native/windows/Broker.cs');(r/'native/windows/Broker.cs').write_bytes(b'evil source\n')
   self.assertEqual(git('status','--porcelain'),'');identity,files=build.source_snapshot(r)
   self.assertTrue(identity['dirty']);self.assertEqual(files['native/windows/Broker.cs'],b'committed source\n')
 def test_excluded_compilation_input_is_not_compiled(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);self.fixture(r);(r/'.git/info/exclude').write_text('hidden.cs\n');(r/'native/windows/hidden.cs').write_bytes(b'evil source\n')
   identity,files=build.source_snapshot(r);self.assertTrue(identity['dirty']);self.assertNotIn('native/windows/hidden.cs',files)
