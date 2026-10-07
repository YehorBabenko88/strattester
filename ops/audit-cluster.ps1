param(
 [string]$Inventory="$PSScriptRoot\cluster-nodes.example.json",
 [string]$IdentityFile="$env:USERPROFILE\.ssh\strattester_control_ed25519"
)
$ErrorActionPreference="Stop"
$nodes=(Get-Content $Inventory -Raw|ConvertFrom-Json).nodes
$script=@'
$os=Get-CimInstance Win32_OperatingSystem
$cpu=Get-CimInstance Win32_Processor|Select-Object -First 1
$legacy=@(Get-CimInstance Win32_Service|Where-Object {$_.Name -match 'Bybit|ClusterGrid|MetaScalp'}|Select-Object Name,State,StartMode,PathName)
[pscustomobject]@{
 Hostname=(hostname); User=(whoami); RAMGB=[math]::Round($os.TotalVisibleMemorySize/1MB,1)
 FreeRAMGB=[math]::Round($os.FreePhysicalMemory/1MB,1); CFreeGB=[math]::Round((Get-PSDrive C).Free/1GB,1)
 Python=((py -0p 2>$null)-join '; '); Git=if(Get-Command git -EA SilentlyContinue){git --version}else{'NOT_FOUND'}
 Postgres=(@(Get-Service 'postgresql*' -EA SilentlyContinue|%{"$($_.Name)/$($_.Status)/$($_.StartType)"})-join '; ')
 Legacy=if($legacy){($legacy|ConvertTo-Json -Compress)}else{'NONE'}
}|ConvertTo-Json -Compress
'@
foreach($n in $nodes){
 if($n.local){ & ([scriptblock]::Create($script)); continue }
 Write-Host "=== $($n.id) ==="
 & ssh -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=8 -i $IdentityFile "$($n.user)@$($n.ssh_host)" "powershell.exe -NoProfile -NonInteractive -Command -" <<< $script
 if($LASTEXITCODE -ne 0){ Write-Warning "$($n.id) audit failed" }
}
