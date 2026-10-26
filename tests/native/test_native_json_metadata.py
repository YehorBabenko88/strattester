import json,os,subprocess,unittest
@unittest.skipUnless(os.name=='nt' and os.environ.get('NATIVE_BROKER'),'compiled Windows broker required')
class NativeMetadataTests(unittest.TestCase):
 def test_cleanup_boolean_metadata_is_canonical_json(self):
  script=r'''$ErrorActionPreference='Stop'
$a=[Reflection.Assembly]::LoadFile($env:NATIVE_BROKER)
$t=$a.GetType('StratTester.Native.OwnerJson',$true)
$d=New-Object 'Collections.Generic.SortedDictionary[string,object]'
$d.Add('claims_preserved',$true);$d.Add('recursive_delete_performed',$false)
$bytes=$t.GetMethod('Canonical',[Reflection.BindingFlags]'Static,NonPublic').Invoke($null,@($d))
[Text.Encoding]::ASCII.GetString($bytes)'''
  r=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=15)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertEqual(json.loads(r.stdout),dict(claims_preserved=True,recursive_delete_performed=False))
