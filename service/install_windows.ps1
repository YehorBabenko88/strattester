param(
 [string]$InstallDir="C:\ProgramData\Strattester",
 [Parameter(Mandatory=$true)][string]$NssmExe,
 [ValidateSet("Worker","ControlWorker","Observer")][string]$Role="Worker"
)

$ErrorActionPreference="Stop"

$CurrentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$CurrentPrincipal = New-Object Security.Principal.WindowsPrincipal($CurrentIdentity)

if(-not $CurrentPrincipal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)){
    throw "Run as Administrator"
}

if(-not(Test-Path $NssmExe)){
    throw "NSSM executable not found: $NssmExe"
}

$py=Join-Path $InstallDir ".venv\Scripts\python.exe"

if(-not(Test-Path $py)){
    throw "Runtime Python not found: $py"
}

function Invoke-NssmStrict {
    param(
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][string]$FailureMessage
    )

    & $NssmExe @Arguments

    if($LASTEXITCODE -ne 0){
        throw "$FailureMessage Exit code: $LASTEXITCODE"
    }
}

function Invoke-NssmBestEffort {
    param(
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )

    & $NssmExe @Arguments 2>$null | Out-Null

    # Deliberately ignore the exit code here.
    # stop/remove may fail simply because the service does not exist.
}

function Remove-ServiceIfPresent {
    param(
        [Parameter(Mandatory=$true)][string]$Name
    )

    Invoke-NssmBestEffort @("stop",$Name,"confirm")
    Invoke-NssmBestEffort @("remove",$Name,"confirm")
}

function Install-ServiceSafe {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Module,
        [Parameter(Mandatory=$true)][string]$Log
    )

    Remove-ServiceIfPresent $Name

    Invoke-NssmStrict `
        -Arguments @("install",$Name,$py,"-m $Module") `
        -FailureMessage "Failed to install service $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"AppDirectory",$InstallDir) `
        -FailureMessage "Failed to configure AppDirectory for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"ObjectName","LocalSystem") `
        -FailureMessage "Failed to configure ObjectName for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"Start","SERVICE_AUTO_START") `
        -FailureMessage "Failed to configure startup mode for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"AppExit","Default","Restart") `
        -FailureMessage "Failed to configure restart policy for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"AppRestartDelay","10000") `
        -FailureMessage "Failed to configure restart delay for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"AppThrottle","5000") `
        -FailureMessage "Failed to configure throttle for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"AppKillProcessTree","1") `
        -FailureMessage "Failed to configure process-tree termination for $Name."

    Invoke-NssmStrict `
        -Arguments @(
            "set",
            $Name,
            "AppStdout",
            (Join-Path $InstallDir "logs\$Log")
        ) `
        -FailureMessage "Failed to configure stdout for $Name."

    Invoke-NssmStrict `
        -Arguments @(
            "set",
            $Name,
            "AppStderr",
            (Join-Path $InstallDir "logs\$Log")
        ) `
        -FailureMessage "Failed to configure stderr for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"AppRotateFiles","1") `
        -FailureMessage "Failed to configure log rotation for $Name."

    Invoke-NssmStrict `
        -Arguments @("set",$Name,"AppRotateBytes","10485760") `
        -FailureMessage "Failed to configure log rotation size for $Name."
}

# Remove services that are not permitted for the selected node role.
if($Role -ne "ControlWorker"){
    Remove-ServiceIfPresent "StrattesterController"
}

if($Role -eq "Observer"){
    Remove-ServiceIfPresent "StrattesterWorker"
    Remove-ServiceIfPresent "StrattesterGuardian"
    exit 0
}

Install-ServiceSafe `
    "StrattesterGuardian" `
    "strattester.service_guardian" `
    "guardian-wrapper.log"

if($Role -eq "ControlWorker"){
    Install-ServiceSafe `
        "StrattesterController" `
        "strattester.service_controller" `
        "controller-wrapper.log"
}

Install-ServiceSafe `
    "StrattesterWorker" `
    "strattester.service_worker" `
    "worker-wrapper.log"

if($Role -eq "ControlWorker"){
    Invoke-NssmStrict `
        -Arguments @("start","StrattesterController") `
        -FailureMessage "Failed to start StrattesterController."
}

Invoke-NssmStrict `
    -Arguments @("start","StrattesterWorker") `
    -FailureMessage "Failed to start StrattesterWorker."

Invoke-NssmStrict `
    -Arguments @("start","StrattesterGuardian") `
    -FailureMessage "Failed to start StrattesterGuardian."
