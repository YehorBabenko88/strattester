param(
 [string]$Inventory="$PSScriptRoot\cluster-nodes.example.json",
 [string]$IdentityFile="$env:USERPROFILE\.ssh\strattester_control_ed25519",
 [switch]$Apply,
 [int]$NodeTimeoutSeconds=30
)
$ErrorActionPreference="Stop"
$plan=@{
 PC1=@{
  Services=@("BybitBacktest","BybitBacktestController","BybitOrderbookRuntime","BybitTelegramController")
  Tasks=@("MetaScalpTelegramBridge")
  Paths=@("C:\Users\Easy\SQL\test","C:\ProgramData\SQL\bybit-trading-system","C:\Users\Easy\AppData\Local\MetaScalpRemote")
 }
 PC2=@{Services=@("BybitClusters");Tasks=@();Paths=@("C:\Users\Leitstelle1\poc")}
 PC3=@{Services=@();Tasks=@();Paths=@()}
 PC4=@{Services=@("BybitBacktestController");Tasks=@();Paths=@("C:\Users\Easy\SQL\test")}
}
$nodes=(Get-Content $Inventory -Raw|ConvertFrom-Json).nodes
foreach($n in $nodes){
 if(!$plan.ContainsKey([string]$n.id)){continue}
 $p=$plan[[string]$n.id]
 Write-Host "=== $($n.id) ==="
 $payload=[pscustomobject]@{Apply=[bool]$Apply;Services=$p.Services;Tasks=$p.Tasks;Paths=$p.Paths}|ConvertTo-Json -Compress
 $remote=@'
param([string]$PlanJson)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$plan=$PlanJson|ConvertFrom-Json
$manifestDir='C:\ProgramData\Strattester\commissioning\legacy'
New-Item -ItemType Directory -Force -Path $manifestDir|Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$foundServices=@();foreach($name in $plan.Services){$s=Get-CimInstance Win32_Service -Filter "Name='$name'" -EA SilentlyContinue;if($s){$foundServices+=$s|select Name,State,StartMode,PathName}}
$foundTasks=@();foreach($name in $plan.Tasks){$t=Get-ScheduledTask -TaskName $name -EA SilentlyContinue;if($t){$foundTasks+=$t|select TaskName,TaskPath,State,@{N='Actions';E={($_.Actions|%{$_.Execute+' '+$_.Arguments}) -join '; '}}}}
$foundPaths=@($plan.Paths|?{Test-Path $_})
$manifest=[pscustomobject]@{Hostname=(hostname);Timestamp=$stamp;Services=$foundServices;Tasks=$foundTasks;Paths=$foundPaths}
$manifestPath=Join-Path $manifestDir "purge-$stamp.json"
$manifest|ConvertTo-Json -Depth 8|Set-Content $manifestPath -Encoding UTF8
if(!$plan.Apply){[pscustomobject]@{Mode='DRY_RUN';Manifest=$manifestPath;Services=$foundServices.Name;Tasks=$foundTasks.TaskName;Paths=$foundPaths}|ConvertTo-Json -Depth 6 -Compress;exit 0}
foreach($name in $foundTasks.TaskName){Unregister-ScheduledTask -TaskName $name -Confirm:$false -EA Stop}
foreach($name in $foundServices.Name){Stop-Service -Name $name -Force -EA SilentlyContinue}
Start-Sleep -Seconds 2
foreach($path in $foundPaths){
 # Exact allowlist only. Never touch active Grid or PostgreSQL paths.
 if($path -like '*BybitClusterGrid*' -or $path -like '*PostgreSQL*'){throw "Protected path refused: $path"}
 Get-CimInstance Win32_Process|?{$_.CommandLine -and $_.CommandLine.Contains($path)}|%{Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue}
}
foreach($name in $foundServices.Name){& sc.exe delete $name|Out-Null}
Start-Sleep -Seconds 2
foreach($path in $foundPaths){Remove-Item -LiteralPath $path -Recurse -Force -EA Stop}
[pscustomobject]@{Mode='APPLIED';Manifest=$manifestPath;RemovedServices=$foundServices.Name;RemovedTasks=$foundTasks.TaskName;RemovedPaths=$foundPaths}|ConvertTo-Json -Depth 6 -Compress
'@
 $plan64=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($payload))
 $wrapper="$([char]36)PlanJson=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('$plan64')); & { $remote } -PlanJson $([char]36)PlanJson"
 $script64=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($wrapper))
 if($n.local){Write-Warning "No LS5 purge plan exists; active Grid is protected.";continue}
 $receiver='$b=[Console]::In.ReadToEnd();$s=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($b));&([scriptblock]::Create($s))'
 $receiver64=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($receiver))
 $out=$script64 | & ssh -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=8 -i $IdentityFile "$($n.user)@$($n.ssh_host)" "powershell.exe -NoProfile -NonInteractive -EncodedCommand $receiver64" 2>&1
 if($LASTEXITCODE -ne 0){throw "Purge failed on $($n.id) with SSH exit code $LASTEXITCODE"}
 $out
}
