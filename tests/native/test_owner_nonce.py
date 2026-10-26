"""Pure validation/guard checks only; NT filesystem probes run in hosted SelfTest."""
import json
import os
from pathlib import Path
import subprocess
import pytest


def invoke(expression):
    broker=os.environ.get('NATIVE_BROKER')
    if os.name!='nt' or not broker:pytest.skip('NATIVE_BROKER required for safe compiled nonce validation')
    env=dict(os.environ)
    for key in ('GITHUB_ACTIONS','RUNNER_ENVIRONMENT','RUNNER_OS'):env.pop(key,None)
    script=r'''
$ErrorActionPreference='Stop'
$assembly=[Reflection.Assembly]::LoadFile($env:NATIVE_BROKER)
$type=$assembly.GetType('StratTester.Native.OwnerNonce',$true)
$flags=[Reflection.BindingFlags]'Static,NonPublic'
function Call([string]$name,[object[]]$values){
 try{$type.GetMethod($name,$flags).Invoke($null,$values);return 'RETURNED'}
 catch{$caught=$_.Exception;while($caught.InnerException){$caught=$caught.InnerException};return $caught.GetType().Name}
}
''' + expression
    result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    return json.loads(result.stdout)


def test_owner_nonce_malformed_values_rejected_before_native_filesystem_access():
    result=invoke(r'''
$good='a'*64
$values=@()
foreach($bad in @('',('a'*63),('A'*64),('../'+('a'*61)),('a'*63+':'))){
 $values+=Call 'Claim' @('C:\MUST_NOT_BE_OPENED',$bad,$good)
 $values+=Call 'Claim' @('C:\MUST_NOT_BE_OPENED',$good,$bad)
}
ConvertTo-Json -InputObject $values -Compress
''')
    assert result==['FormatException']*10


def test_owner_nonce_namespace_aliases_rejected_before_native_filesystem_access():
    result=invoke(r'''
$good='a'*64
$values=@()
foreach($bad in @('', 'relative', '\\server\share\ledger', '\\?\C:\ledger', '\\.\C:\ledger', 'C:\ledger:stream', 'C:\x\..\ledger', 'C:\x\.', 'C:\CON', 'C:\COM1.txt', 'C:\LPT¹', 'C:\ledger.', 'C:\ledger ', 'C:/ledger', 'C:\x\\ledger')){
 $values+=Call 'Claim' @($bad,$good,$good)
}
ConvertTo-Json -InputObject $values -Compress
''')
    assert result==['FormatException']*15


def test_owner_nonce_selftest_refuses_physical_host_before_native_filesystem_access():
    assert invoke("ConvertTo-Json -InputObject (Call 'SelfTest' @()) -Compress")=='InvalidOperationException'
