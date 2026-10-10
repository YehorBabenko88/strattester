param([string]$InstallDir="C:\ProgramData\Strattester",[Parameter(Mandatory=$true)][string]$NssmExe,[switch]$DeleteData)
$ErrorActionPreference="Stop"
foreach($name in @("StrattesterGuardian","StrattesterController","StrattesterWorker")){
 if(!(Get-Service -Name $name -ErrorAction SilentlyContinue)){continue}
 & $NssmExe stop $name confirm 2>$null | Out-Null
 if($LASTEXITCODE -ne 0){throw "Failed to stop $name; services/data were not fully removed."}
 & $NssmExe remove $name confirm 2>$null | Out-Null
 if($LASTEXITCODE -ne 0){throw "Failed to remove $name; data deletion refused."}
}
if($DeleteData){
 $answer=Read-Host "Type DELETE-DATA to permanently remove data/state/results"
 if($answer -eq "DELETE-DATA"){foreach($d in @("data","state","results")){Remove-Item (Join-Path $InstallDir $d) -Recurse -Force -ErrorAction SilentlyContinue}}
}
Write-Host "Services removed. Data preserved unless explicitly deleted."
