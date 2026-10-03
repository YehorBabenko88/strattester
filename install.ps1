param(
 [string]$InstallDir = "C:\ProgramData\Strattester",
 [string]$PythonExe = "",
 [string]$NssmExe = "",
 [switch]$DryRun
)
$ErrorActionPreference="Stop"
function Step([string]$m){ Write-Host "[Strattester] $m" }
if(-not $PythonExe){
 $cmd=Get-Command python -ErrorAction SilentlyContinue
 if(-not $cmd){ throw "Python 3.11+ not found. Install Python or pass -PythonExe." }
 $PythonExe=$cmd.Source
}
& $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)"
if($LASTEXITCODE -ne 0){ throw "Python 3.11+ required." }
if($DryRun){
 Step "DRY RUN: no Windows service will be installed or started."
 Step "Python: $PythonExe"
 & $PythonExe -m strattester.preflight_cli --root $InstallDir
 if($LASTEXITCODE -ne 0){ throw "Preflight failed." }
 Step "Preflight passed. Data/state/results/logs preserved."
 exit 0
}
New-Item -ItemType Directory -Force $InstallDir | Out-Null
foreach($d in @("data","state","results","logs","config","releases")){New-Item -ItemType Directory -Force (Join-Path $InstallDir $d)|Out-Null}
$venv=Join-Path $InstallDir ".venv"
if(-not(Test-Path $venv)){ & $PythonExe -m venv $venv }
& (Join-Path $venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $venv "Scripts\python.exe") -m pip install .
& (Join-Path $venv "Scripts\python.exe") -m strattester.preflight_cli --root $InstallDir --network
if($LASTEXITCODE -ne 0){ throw "Installed environment preflight failed; services were not touched." }
if($NssmExe){ & "$PSScriptRoot\service\install_windows.ps1" -InstallDir $InstallDir -NssmExe $NssmExe }
Step "Installation complete"
