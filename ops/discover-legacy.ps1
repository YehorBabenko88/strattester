param(
 [string]$Inventory="$PSScriptRoot\cluster-nodes.example.json",
 [string]$IdentityFile="$env:USERPROFILE\.ssh\strattester_control_ed25519",
 [int]$NodeTimeoutSeconds=30
)
$ErrorActionPreference="Stop"
$nodes=(Get-Content $Inventory -Raw|ConvertFrom-Json).nodes
$probe=@'
$servicePattern='Bybit|ClusterGrid|MetaScalp'; $pathPattern='Bybit|ClusterGrid|MetaScalp|bybit-trading-system|\\SQL\\test|\\poc\\'
$services=@(Get-CimInstance Win32_Service|?{$_.Name -match $servicePattern -or $_.PathName -match $pathPattern}|select Name,State,StartMode,PathName)
$tasks=@(Get-ScheduledTask -EA SilentlyContinue|?{$_.TaskName -match $servicePattern -or (($_.Actions.Execute+' '+$_.Actions.Arguments) -match $pathPattern)}|select TaskName,TaskPath,State,@{N='Actions';E={($_.Actions|%{$_.Execute+' '+$_.Arguments}) -join '; '}})
$processes=@(Get-CimInstance Win32_Process|?{$_.CommandLine -match $pathPattern}|select ProcessId,Name,CommandLine)
$paths=@('C:\ProgramData\SQL\bybit-trading-system','C:\ProgramData\BybitClusterGrid','C:\Program Files\BybitClusterGrid','C:\Users\Easy\SQL\test','C:\Users\Leitstelle1\poc')|?{Test-Path $_}
$db=@(); $psql=Get-Command psql.exe -EA SilentlyContinue
if($psql){try{$db=@(& $psql.Source -U postgres -d postgres -Atc "select datname from pg_database where datistemplate=false order by 1" 2>$null)}catch{}}
[pscustomobject]@{Hostname=(hostname);Services=$services;ScheduledTasks=$tasks;Processes=$processes;LegacyPaths=$paths;PostgresDatabases=$db}|ConvertTo-Json -Depth 8 -Compress
'@
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe))
foreach($n in $nodes){
 Write-Host "=== $($n.id) ==="
 if($n.local){&([scriptblock]::Create($probe));continue}
 $stdout=[IO.Path]::GetTempFileName();$stderr=[IO.Path]::GetTempFileName()
 try{
  $args=@("-o","BatchMode=yes","-o","PasswordAuthentication=no","-o","ConnectTimeout=8","-i",$IdentityFile,"$($n.user)@$($n.ssh_host)","powershell.exe -NoProfile -NonInteractive -EncodedCommand $encoded")
  $p=Start-Process ssh.exe -ArgumentList $args -NoNewWindow -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  if(-not $p.WaitForExit($NodeTimeoutSeconds*1000)){
   try{$p.Kill()}catch{}
   Write-Warning "$($n.id) discovery timed out after $NodeTimeoutSeconds seconds"
   continue
  }
  $out=(Get-Content $stdout -Raw -EA SilentlyContinue);$err=(Get-Content $stderr -Raw -EA SilentlyContinue)
  if($p.ExitCode -ne 0){Write-Warning "$($n.id) discovery failed: $err$out";continue}
  if($out){$out.Trim()}
 } finally {Remove-Item $stdout,$stderr -Force -EA SilentlyContinue}
}
