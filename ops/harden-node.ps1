param([string]$InstallDir="C:\ProgramData\Strattester")
$ErrorActionPreference="Stop"
if(-not([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw "Run as Administrator"}
New-Item -ItemType Directory -Force -Path $InstallDir|Out-Null
# Infrastructure data is controlled by SYSTEM/Administrators, not interactive standard users.
& icacls.exe $InstallDir /inheritance:r | Out-Null
& icacls.exe $InstallDir /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null
if($LASTEXITCODE -ne 0){throw "Failed to harden StratTester ACL"}
# OpenSSH: key-only. Existing administrator_authorized_keys is preserved.
$sshd="C:\ProgramData\ssh\sshd_config"
if(Test-Path $sshd){
 $text=Get-Content $sshd -Raw
 $directives=@{"PasswordAuthentication"="no";"PubkeyAuthentication"="yes"}
 foreach($k in $directives.Keys){
  $line="$k $($directives[$k])"
  if($text -match "(?m)^\s*#?\s*$k\s+.*$"){$text=[regex]::Replace($text,"(?m)^\s*#?\s*$k\s+.*$",$line)}
  else{$text+="`r`n$line"}
 }
 Set-Content -Path $sshd -Value $text -Encoding ascii
 & sshd.exe -t
 if($LASTEXITCODE -ne 0){throw "sshd_config validation failed"}
 Restart-Service sshd
}
# SSH is reachable only through Tailscale CGNAT; do not expose TCP/22 to LAN/Internet.
Get-NetFirewallRule -DisplayName "Strattester SSH via Tailscale" -EA SilentlyContinue|Remove-NetFirewallRule
New-NetFirewallRule -DisplayName "Strattester SSH via Tailscale" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22 -RemoteAddress "100.64.0.0/10" -Profile Any|Out-Null
[pscustomobject]@{ACL="SYSTEM+Administrators";SSH="key-only";SSHFirewall="100.64.0.0/10"}|ConvertTo-Json -Compress
