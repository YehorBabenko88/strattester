param([string]$InstallDir="C:\Strattester",[Parameter(Mandatory=$true)][string]$NssmExe,[switch]$DeleteData)
$ErrorActionPreference="Stop"
foreach($name in @("StrattesterWorker","StrattesterController")){
 & $NssmExe stop $name confirm 2>$null | Out-Null
 & $NssmExe remove $name confirm 2>$null | Out-Null
}
if($DeleteData){
 $answer=Read-Host "Type DELETE-DATA to permanently remove data/state/results"
 if($answer -eq "DELETE-DATA"){foreach($d in @("data","state","results")){Remove-Item (Join-Path $InstallDir $d) -Recurse -Force -ErrorAction SilentlyContinue}}
}
Write-Host "Services removed. Data preserved unless explicitly deleted."
