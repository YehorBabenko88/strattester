param(
    [ValidateSet("Worker","Control","Observer")][string]$Role = "Worker",
    [string]$ControlPublicKey = "",
    [switch]$InstallTailscale,
    [switch]$InstallGit
)
$ErrorActionPreference = "Stop"
function Step($m){ Write-Host "[bootstrap] $m" }
function IsAdmin {
    $id=[Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
if(-not (IsAdmin)){ throw "Run PowerShell as Administrator." }

Step "host=$(hostname) role=$Role"
$cap=Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if($cap.State -ne "Installed"){ Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null }
Set-Service sshd -StartupType Automatic
Start-Service sshd

if(-not (Get-NetFirewallRule -DisplayName "Strattester SSH via Tailscale" -ErrorAction SilentlyContinue)){
    New-NetFirewallRule -DisplayName "Strattester SSH via Tailscale" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22 -RemoteAddress 100.64.0.0/10 -Profile Any | Out-Null
}
if($InstallTailscale -and -not (Get-Command tailscale -ErrorAction SilentlyContinue)){
    if(-not (Get-Command winget -ErrorAction SilentlyContinue)){ throw "winget is required to install Tailscale." }
    winget install --id Tailscale.Tailscale -e --source winget --accept-package-agreements --accept-source-agreements
}
if($InstallGit -and -not (Get-Command git -ErrorAction SilentlyContinue)){
    if(-not (Get-Command winget -ErrorAction SilentlyContinue)){ throw "winget is required to install Git." }
    winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
}
if($ControlPublicKey){
    if($ControlPublicKey -notmatch '^ssh-ed25519\s+'){ throw "Only an ssh-ed25519 public key is accepted." }
    $f='C:\ProgramData\ssh\administrators_authorized_keys'
    if(-not(Test-Path $f)){ New-Item -ItemType File -Path $f -Force | Out-Null }
    $cur=@(Get-Content $f -ErrorAction SilentlyContinue)
    if($cur -notcontains $ControlPublicKey){ Add-Content $f $ControlPublicKey -Encoding ascii }
    icacls $f /inheritance:r | Out-Null
    icacls $f /grant:r 'SYSTEM:F' | Out-Null
    icacls $f /grant '*S-1-5-32-544:F' | Out-Null
    Restart-Service sshd
}
$ts=(Get-Command tailscale -ErrorAction SilentlyContinue)
$ip=if($ts){ (tailscale ip -4 2>$null | Select-Object -First 1) }else{ "" }
[pscustomobject]@{
    Hostname=(hostname); Role=$Role; User=(whoami); TailscaleIPv4=$ip
    SSHD=(Get-Service sshd).Status; Git=if(Get-Command git -ErrorAction SilentlyContinue){"present"}else{"missing"}
} | Format-List
if(-not $ip){ Step "Tailscale is not authenticated yet. Run: tailscale up" }
Step "Local bootstrap complete. ESET firewall policy must still allow TCP/22 from trusted Tailscale peers."
