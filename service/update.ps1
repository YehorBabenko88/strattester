param([string]$InstallDir="C:\Strattester",[Parameter(Mandatory=$true)][string]$Commit)
$ErrorActionPreference="Stop"
Write-Host "[Strattester] Requested immutable update $Commit"
Write-Host "[Strattester] Update must be staged and health-checked before service activation."
# Network retrieval is intentionally delegated to the Python updater/release provider.
