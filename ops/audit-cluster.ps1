param(
    [string]$Inventory = "$PSScriptRoot\cluster-nodes.example.json",
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\strattester_control_ed25519"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Inventory)) { throw "Inventory not found: $Inventory" }
if (-not (Test-Path $IdentityFile)) { throw "SSH identity not found: $IdentityFile" }
$nodes = (Get-Content $Inventory -Raw | ConvertFrom-Json).nodes
$remoteScript = @'
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$legacy = @(Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'Bybit|ClusterGrid|MetaScalp|Strattester' } | Select-Object Name, State, StartMode, PathName)
[pscustomobject]@{
 Hostname=(hostname); User=(whoami); CPU=$cpu.Name; LogicalProcessors=$cpu.NumberOfLogicalProcessors
 RAMGB=[math]::Round($os.TotalVisibleMemorySize/1MB,1); FreeRAMGB=[math]::Round($os.FreePhysicalMemory/1MB,1); CFreeGB=[math]::Round((Get-PSDrive C).Free/1GB,1)
 Python=((py -0p 2>$null)-join '; '); Git=if(Get-Command git -ErrorAction SilentlyContinue){git --version}else{'NOT_FOUND'}
 Postgres=(@(Get-Service "postgresql*" -ErrorAction SilentlyContinue | ForEach-Object {"$($_.Name)/$($_.Status)/$($_.StartType)"}) -join "; ")
 Legacy=if($legacy){($legacy|ConvertTo-Json -Compress)}else{'NONE'}
} | ConvertTo-Json -Compress
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remoteScript))
foreach ($n in $nodes) {
 Write-Host "=== $($n.id) ==="
 if ($n.local) { & ([scriptblock]::Create($remoteScript)); continue }
 $destination = "$($n.user)@$($n.ssh_host)"
 $sshArgs = @("-o","BatchMode=yes","-o","PasswordAuthentication=no","-o","ConnectTimeout=8","-i",$IdentityFile,$destination,"powershell.exe -NoProfile -NonInteractive -EncodedCommand $encoded")
 $output = & ssh @sshArgs 2>&1
 if ($LASTEXITCODE -ne 0) { Write-Warning "$($n.id) audit failed: $output"; continue }
 $output
}
