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
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$InformationPreference='SilentlyContinue'
$plan=$PlanJson|ConvertFrom-Json
$manifestDir='C:\ProgramData\Strattester\commissioning\legacy'
New-Item -ItemType Directory -Force -Path $manifestDir|Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$foundServices=@();if(@($plan.Services).Count -gt 0){foreach($name in $plan.Services){$s=Get-CimInstance Win32_Service -Filter "Name='$name'" -EA SilentlyContinue;if($s){$foundServices+=$s|select Name,State,StartMode,PathName}}}
$foundTasks=@();if(@($plan.Tasks).Count -gt 0){foreach($name in $plan.Tasks){$t=Get-ScheduledTask -TaskName $name -EA SilentlyContinue;if($t){$foundTasks+=$t|select TaskName,TaskPath,State,@{N='Actions';E={($_.Actions|%{$_.Execute+' '+$_.Arguments}) -join '; '}}}}}
$foundPaths=@();if(@($plan.Paths).Count -gt 0){$foundPaths=@($plan.Paths|?{Test-Path $_})}
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
 $psi=New-Object System.Diagnostics.ProcessStartInfo
 $psi.FileName='ssh.exe'
 $psi.UseShellExecute=$false
 $psi.RedirectStandardInput=$true
 $psi.RedirectStandardOutput=$true
 $psi.RedirectStandardError=$true
 $psi.CreateNoWindow=$true
 $psi.Arguments="-o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=8 -i `"$IdentityFile`" $($n.user)@$($n.ssh_host) powershell.exe -NoProfile -NonInteractive -EncodedCommand $receiver64"
 $proc=New-Object System.Diagnostics.Process
 $proc.StartInfo=$psi
 if(!$proc.Start()){throw "Failed to start SSH for $($n.id)"}
 $proc.StandardInput.Write($script64)
 $proc.StandardInput.Close()
 if(!$proc.WaitForExit($NodeTimeoutSeconds*1000)){
  try{$proc.Kill()}catch{}
  try{$proc.WaitForExit(5000)|Out-Null}catch{}
  throw "Purge timed out on $($n.id) after $NodeTimeoutSeconds seconds"
 }
 $stdout=$proc.StandardOutput.ReadToEnd()
 $stderr=$proc.StandardError.ReadToEnd()
 if($proc.ExitCode -ne 0){throw "Purge failed on $($n.id) with SSH exit code $($proc.ExitCode): $stderr"}
 if($stderr.Trim()){Write-Warning "$($n.id) stderr: $($stderr.Trim())"}
 $out=@($stdout -split "[`r`n]+"|?{$_})
 $out
}
