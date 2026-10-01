param([string]$InstallDir="C:\Strattester",[Parameter(Mandatory=$true)][string]$NssmExe)
$ErrorActionPreference="Stop"
if(-not([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw "Run as Administrator"}
$py=Join-Path $InstallDir ".venv\Scripts\python.exe"
function Install-ServiceSafe($name,$module,$log){
 & $NssmExe stop $name confirm 2>$null | Out-Null
 & $NssmExe remove $name confirm 2>$null | Out-Null
 & $NssmExe install $name $py "-m $module"
 & $NssmExe set $name AppDirectory $InstallDir
 & $NssmExe set $name Start SERVICE_AUTO_START
 & $NssmExe set $name AppExit Default Restart
 & $NssmExe set $name AppRestartDelay 10000
 & $NssmExe set $name AppThrottle 5000
 & $NssmExe set $name AppKillProcessTree 1
 & $NssmExe set $name AppStdout (Join-Path $InstallDir "logs\$log")
 & $NssmExe set $name AppStderr (Join-Path $InstallDir "logs\$log")
 & $NssmExe set $name AppRotateFiles 1
 & $NssmExe set $name AppRotateBytes 10485760
}
Install-ServiceSafe "StrattesterController" "strattester.service_controller" "controller-wrapper.log"
Install-ServiceSafe "StrattesterWorker" "strattester.service_worker" "worker-wrapper.log"
& $NssmExe start StrattesterController
& $NssmExe start StrattesterWorker
