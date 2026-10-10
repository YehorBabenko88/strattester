param(
 [string]$InstallDir = "C:\ProgramData\Strattester",
 [string]$PythonExe = "",
 [string]$NssmExe = "",
 [switch]$DryRun
)

$ErrorActionPreference="Stop"

function Step([string]$m){
 Write-Host "[Strattester] $m"
}

function Run-Native {
 param(
  [Parameter(Mandatory=$true)][string]$Executable,
  [Parameter(Mandatory=$true)][string[]]$Arguments,
  [Parameter(Mandatory=$true)][string]$FailureMessage
 )

 & $Executable @Arguments

 if($LASTEXITCODE -ne 0){
  throw "$FailureMessage Exit code: $LASTEXITCODE"
 }
}

if(-not $PythonExe){
 $cmd=Get-Command python -ErrorAction SilentlyContinue
 if(-not $cmd){
  throw "Python 3.11+ not found. Install Python or pass -PythonExe."
 }
 $PythonExe=$cmd.Source
}

Run-Native `
 -Executable $PythonExe `
 -Arguments @(
  "-c",
  "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)"
 ) `
 -FailureMessage "Python 3.11+ required."

if($DryRun){
 Step "DRY RUN: validation only; filesystem and services will not be modified."
 Step "Python: $PythonExe"

 Run-Native `
  -Executable $PythonExe `
  -Arguments @(
   "-c",
   "import sys; sys.path.insert(0, r'$PSScriptRoot'); import strattester; print('Strattester source import: OK')"
  ) `
  -FailureMessage "Strattester source import failed."

 Step "Dry-run validation passed. No files, directories, databases or services were created."
 exit 0
}

New-Item -ItemType Directory -Force $InstallDir | Out-Null

foreach($d in @("data","state","results","logs","config","releases")){
 New-Item -ItemType Directory -Force (Join-Path $InstallDir $d) | Out-Null
}

$venv=Join-Path $InstallDir ".venv"

if(-not(Test-Path $venv)){
 Run-Native `
  -Executable $PythonExe `
  -Arguments @("-m","venv",$venv) `
  -FailureMessage "Virtual environment creation failed; services were not touched."
}

$VenvPython=Join-Path $venv "Scripts\python.exe"

if(-not(Test-Path $VenvPython)){
 throw "Virtual environment Python not found: $VenvPython"
}

Run-Native `
 -Executable $VenvPython `
 -Arguments @("-m","pip","install","--upgrade","pip") `
 -FailureMessage "pip upgrade failed; services were not touched."

Run-Native `
 -Executable $VenvPython `
 -Arguments @("-m","pip","install",$PSScriptRoot) `
 -FailureMessage "Strattester package installation failed; services were not touched."

Run-Native `
 -Executable $VenvPython `
 -Arguments @(
  "-m",
  "strattester.preflight_cli",
  "--root",
  $InstallDir,
  "--network"
 ) `
 -FailureMessage "Installed environment preflight failed; services were not touched."

Step "Running isolated one-shot worker smoke test"

Run-Native `
 -Executable $VenvPython `
 -Arguments @(
  "-m",
  "strattester.smoke_cli",
  "--root",
  $InstallDir
 ) `
 -FailureMessage "Worker smoke test failed; services were not touched."

Step "Running isolated BTCUSDT market-data smoke test"

Run-Native `
 -Executable $VenvPython `
 -Arguments @(
  "-m",
  "strattester.marketdata.download_smoke_cli",
  "--root",
  (Join-Path $InstallDir "state"),
  "--minutes",
  "10"
 ) `
 -FailureMessage "Market-data smoke test failed; services were not touched."

if($NssmExe){
 & "$PSScriptRoot\service\install_windows.ps1" `
  -InstallDir $InstallDir `
  -NssmExe $NssmExe
}

Step "Installation complete"
