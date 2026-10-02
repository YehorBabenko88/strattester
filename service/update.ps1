param([string]$InstallDir="C:\ProgramData\Strattester",[Parameter(Mandatory=$true)][string]$Commit)
$ErrorActionPreference="Stop"
Write-Host "[Strattester] Requested immutable update $Commit"
Write-Host "[Strattester] Update must be staged and health-checked before service activation."
