import json,os,subprocess,unittest
@unittest.skipUnless(os.name=='nt' and os.environ.get('NATIVE_BROKER'),'compiled Windows broker required')
class NativeMetadataTests(unittest.TestCase):
 def test_cleanup_boolean_metadata_is_canonical_json(self):
  script=r'''$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
public static class MetadataFixture {
 public static string Run(string path) {
  var d=new System.Collections.Generic.SortedDictionary<string,object>(System.StringComparer.Ordinal);
  d.Add("claims_preserved",true);d.Add("recursive_delete_performed",false);
  var t=System.Reflection.Assembly.LoadFile(path).GetType("StratTester.Native.OwnerJson",true);
  var m=t.GetMethod("Canonical",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic);
  return System.Text.Encoding.ASCII.GetString((byte[])m.Invoke(null,new object[]{d}));
 }
}
'@
[MetadataFixture]::Run($env:NATIVE_BROKER)'''
  r=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=15)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertEqual(json.loads(r.stdout),dict(claims_preserved=True,recursive_delete_performed=False))
