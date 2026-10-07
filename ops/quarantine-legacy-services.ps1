param(
 [string]$Inventory="$PSScriptRoot\cluster-nodes.example.json",
 [string]$IdentityFile="$env:USERPROFILE\.ssh\strattester_control_ed25519",
 [switch]$Apply
)
$ErrorActionPreference="Stop"
$nodes=(Get-Content $Inventory -Raw|ConvertFrom-Json).nodes
$remoteScript=@'
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$root="C:\ProgramData\Strattester\commissioning\legacy"
New-Item -ItemType Directory -Force -Path $root|Out-Null
$services=@(Get-CimInstance Win32_Service|Where-Object {$_.Name -match 'Bybit|ClusterGrid|MetaScalp' -and $_.Name -notmatch '^Strattester'})
$snapshot=@($services|Select-Object Name,DisplayName,State,StartMode,PathName,StartName)
$snapshotPath=Join-Path $root "legacy-services-$stamp.json"
$snapshot|ConvertTo-Json -Depth 4|Set-Content -Encoding UTF8 $snapshotPath
$changed=@()
foreach($s in $services){
 if($s.StartMode -eq "Auto"){
  if($s.State -ne "Stopped"){ Stop-Service -Name $s.Name -Force -ErrorAction Stop }
  Set-Service -Name $s.Name -StartupType Disabled
  $changed+=$s.Name
 }
}
[pscustomobject]@{Hostname=(hostname);Snapshot=$snapshotPath;Found=@($services).Count;Disabled=$changed}|ConvertTo-Json -Compress
'@
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteScript))
foreach($n in $nodes){
 Write-Host "=== $($n.id) ==="
 if(-not $Apply){
  if($n.local){$legacy=@(Get-CimInstance Win32_Service|?{$_.Name -match "Bybit|ClusterGrid|MetaScalp"}|select Name,State,StartMode,PathName)}
  else {$q=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes('Get-CimInstance Win32_Service|?{$_.Name -match "Bybit|ClusterGrid|MetaScalp"}|select Name,State,StartMode,PathName|ConvertTo-Json -Compress')); $legacy=& ssh -o BatchMode=yes -i $IdentityFile "$($n.user)@$($n.ssh_host)" "powershell.exe -NoProfile -EncodedCommand $q"}
  $legacy; continue
 }
 if($n.local){&([scriptblock]::Create($remoteScript));continue}
 & ssh -o BatchMode=yes -i $IdentityFile "$($n.user)@$($n.ssh_host)" "powershell.exe -NoProfile -EncodedCommand $encoded"
 if($LASTEXITCODE -ne 0){throw "Quarantine failed on $($n.id)"}
}
