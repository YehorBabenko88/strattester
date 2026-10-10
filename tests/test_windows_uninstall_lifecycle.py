import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform!='win32',reason='PowerShell lifecycle harness')
def test_uninstaller_stops_guardian_before_other_services(tmp_path):
    script=Path(__file__).resolve().parents[1]/'service'/'uninstall_windows.ps1'
    log=tmp_path/'commands.log'
    fake=tmp_path/'fake-nssm.ps1'
    fake.write_text("param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)\n"
                    f"($Rest -join ' ') | Add-Content -LiteralPath '{log.as_posix()}'\n"
                    "$global:LASTEXITCODE=0\n",encoding='utf-8')
    harness=("function Get-Service { [CmdletBinding()] param([string]$Name) [pscustomobject]@{Name=$Name} }; "
             f"& '{script.as_posix()}' -InstallDir '{tmp_path.as_posix()}' -NssmExe '{fake.as_posix()}'")
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',harness],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    commands=log.read_text(encoding='utf-8-sig').splitlines()
    assert commands[:2]==['stop StrattesterGuardian confirm','remove StrattesterGuardian confirm']
    assert {c.split()[1] for c in commands}=={'StrattesterGuardian','StrattesterWorker','StrattesterController'}
