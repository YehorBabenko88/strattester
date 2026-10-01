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
if($DryRun){
 Step "DRY RUN: install into $InstallDir"
 Step "Python: $PythonExe"
 Step "Data/state/results/logs will be preserved outside releases."
 exit 0
}
New-Item -ItemType Directory -Force $InstallDir | Out-Null
foreach($d in @("data","state","results","logs","config","releases")){New-Item -ItemType Directory -Force (Join-Path $InstallDir $d)|Out-Null}
$venv=Join-Path $InstallDir ".venv"
if(-not(Test-Path $venv)){ & $PythonExe -m venv $venv }
& (Join-Path $venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $venv "Scripts\python.exe") -m pip install .
if($NssmExe){ & "$PSScriptRoot\service\install_windows.ps1" -InstallDir $InstallDir -NssmExe $NssmExe }
Step "Installation complete"
