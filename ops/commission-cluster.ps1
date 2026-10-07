param(
    [Parameter(Mandatory=$true)][string]$Inventory = "$PSScriptRoot\cluster-nodes.example.json",
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\strattester_control_ed25519",
    [switch]$CheckOnly
)
$ErrorActionPreference="Stop"
$nodes=Get-Content $Inventory -Raw | ConvertFrom-Json
if(-not(Test-Path $IdentityFile)){ throw "SSH identity not found: $IdentityFile" }
$results=@()
foreach($n in $nodes.nodes){
    if($n.local){ continue }
    $dest="$($n.user)@$($n.ssh_host)"
    Write-Host "=== $($n.id) $dest ==="
    $tcp=Test-NetConnection $n.tailscale_ip -Port 22 -WarningAction SilentlyContinue
    if(-not $tcp.TcpTestSucceeded){
        $results += [pscustomobject]@{Node=$n.id;TCP22=$false;SSH=$false;Hostname="";Error="TCP/22 blocked"}
        continue
    }
    $out=& ssh -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=8 -i $IdentityFile $dest "hostname" 2>&1
    $ok=($LASTEXITCODE -eq 0)
    $results += [pscustomobject]@{Node=$n.id;TCP22=$true;SSH=$ok;Hostname=if($ok){"$out"}else{""};Error=if($ok){""}else{"$out"}}
}
$results | Format-Table -AutoSize
$failed=@($results|Where-Object{-not $_.SSH})
Write-Host "SSH success: $($results.Count-$failed.Count)/$($results.Count)"
if($failed.Count){ exit 2 }
