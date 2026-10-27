# Read-only G0 metadata collector. No DB connections, process control, service
# mutations, installs, outbound requests, or filesystem writes. Emits JSON only.
$ErrorActionPreference='Stop'
$node=Get-CimInstance Win32_ComputerSystemProduct
$identity=[System.Text.Encoding]::UTF8.GetBytes($env:COMPUTERNAME+'|'+$node.UUID)
$nodeHash=[Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($identity)).ToLowerInvariant()
$os=Get-CimInstance Win32_OperatingSystem
$root=(Get-Location).Path
$acl=Get-Acl -LiteralPath $root
$ports=Get-NetTCPConnection -State Listen | ForEach-Object {
    [ordered]@{port=$_.LocalPort;pid=$_.OwningProcess;scope=$(if($_.LocalAddress -in @('127.0.0.1','::1')){'loopback'}elseif($_.LocalAddress -in @('0.0.0.0','::')){'wildcard'}else{'interface-redacted'})}
}
[ordered]@{
    schema=1;phase='G0_READ_ONLY';captured_utc=(Get-Date).ToUniversalTime().ToString('o')
    node_name=$env:COMPUTERNAME;node_identity_sha256=$nodeHash
    os=$os | Select-Object Caption,Version,BuildNumber,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory
    cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
    disk=Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace
    services=Get-Service | ForEach-Object {[ordered]@{name=$_.Name;status=[string]$_.Status;start_type=[string]$_.StartType}}
    processes=Get-Process | Select-Object Id,ProcessName,WorkingSet64
    listeners=$ports
    sandbox=[ordered]@{path=$root;reparse_point=[bool]((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint);acl_protected=$acl.AreAccessRulesProtected;acl_rule_count=$acl.Access.Count;confinement_proven=$false}
    secrets='No environment dump, command lines, connection strings, passwords or tokens collected'
    g1='NOT_AUTHORIZED'
} | ConvertTo-Json -Depth 7

