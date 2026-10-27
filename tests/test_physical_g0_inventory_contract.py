"""Exercise the collector only with mocked OS observations, never host inventory."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


def collect(tmp_path, *, fail_udp=False, shell='pwsh'):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f'{shell} unavailable: mocked PowerShell contract only')
    script = Path(__file__).resolve().parents[1] / 'scripts/physical_g0_inventory.ps1'
    # Every inventory command is replaced. Unexpected source commands fail
    # through the command allowlist below before this harness is executed.
    allowed = {'Get-CimInstance', 'Get-Location', 'Get-Acl', 'Get-NetTCPConnection',
               'Get-NetUDPEndpoint', 'Get-Service', 'Get-Process', 'Get-Item', 'Get-Date'}
    import re
    commands = set(re.findall(r'\bGet-[A-Za-z]+', script.read_text()))
    assert commands <= allowed, commands - allowed
    udp = "throw 'denied secret-DSN'" if fail_udp else "[pscustomobject]@{LocalPort=5353;OwningProcess=7;LocalAddress='::'}"
    harness = r'''
$env:COMPUTERNAME='DISPOSABLE_FIXTURE'
function Get-CimInstance { param($ClassName,$Filter)
 switch($ClassName) {
 'Win32_ComputerSystemProduct' {[pscustomobject]@{UUID='fixture-uuid'}}
 'Win32_OperatingSystem' {[pscustomobject]@{Caption='fixture-os';Version='1';BuildNumber='2';OSArchitecture='64-bit';TotalVisibleMemorySize=4194304;FreePhysicalMemory=3000000}}
 'Win32_Processor' {[pscustomobject]@{Name='fixture-cpu';NumberOfCores=2;NumberOfLogicalProcessors=4}}
 'Win32_LogicalDisk' {[pscustomobject]@{DeviceID='C:';Size=100000;FreeSpace=80000}}
 'Win32_VideoController' {[pscustomobject]@{Name='fixture-gpu';DriverVersion='fixture-driver';AdapterRAM=1024}}
 default {throw 'unexpected CIM query'}
 }}
function Get-Location {[pscustomobject]@{Path='C:\FIXTURE'}}
function Get-Acl {param($LiteralPath) [pscustomobject]@{AreAccessRulesProtected=$true;Access=@(1)}}
function Get-Item {param($LiteralPath) [pscustomobject]@{Attributes=[IO.FileAttributes]::Directory}}
function Get-NetTCPConnection {param($State) [pscustomobject]@{LocalPort=5432;OwningProcess=7;LocalAddress='127.0.0.1'}}
function Get-NetUDPEndpoint { UDP_BODY }
function Get-Service {[pscustomobject]@{Name='fixture-service';Status='Running';StartType='Manual'}}
function Get-Process {[pscustomobject]@{Id=7;ProcessName='fixture-db';WorkingSet64=1024}}
'''.replace('UDP_BODY', udp)
    harness += "\n& '" + script.as_posix().replace("'", "''") + "'\n"
    target = tmp_path / f'mocked-{shell}.ps1'
    target.write_text(harness, encoding='utf-8-sig')
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-File', str(target)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'secret-DSN' not in result.stdout
    return json.loads(result.stdout)


def test_udp_gpu_and_missing_facts_are_explicit(tmp_path):
    report = collect(tmp_path)
    assert report['udp_endpoints'][0]['port'] == 5353
    assert report['observations']['udp'] == 'OBSERVED'
    assert report['gpu'][0]['DriverVersion'] == 'fixture-driver'
    assert report['g0_readiness'] == 'BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE'
    assert report['unverified']['cuda_runtime'] == 'NOT_PROBED'
    assert report['unverified']['process_db_ownership'] == 'OWNER_ATTESTATION_REQUIRED'
    assert report['g1'] == 'NOT_AUTHORIZED'


def test_unavailable_observation_is_not_empty_pass_and_does_not_leak_error(tmp_path):
    report = collect(tmp_path, fail_udp=True)
    assert report['udp_endpoints'] == []
    assert report['observations']['udp'] == 'UNAVAILABLE'
    assert report['g0_readiness'].startswith('BLOCKED')


def test_windows_powershell_51_hashing_uses_compatible_primitives(tmp_path):
    report = collect(tmp_path, shell='powershell.exe')
    import hashlib
    assert report['node_identity_sha256'] == hashlib.sha256(b'DISPOSABLE_FIXTURE|fixture-uuid').hexdigest()
