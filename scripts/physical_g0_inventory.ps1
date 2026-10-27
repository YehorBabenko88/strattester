# Read-only G0 metadata collector. No DB connections, process control, service
# mutations, installs, outbound requests, or filesystem writes. Emits JSON only.
$ErrorActionPreference='Stop'
$node=Get-CimInstance Win32_ComputerSystemProduct
$identity=[System.Text.Encoding]::UTF8.GetBytes($env:COMPUTERNAME+'|'+$node.UUID)
$hasher=[System.Security.Cryptography.SHA256]::Create()
try {$nodeHash=([BitConverter]::ToString($hasher.ComputeHash($identity))).Replace('-','').ToLowerInvariant()}
finally {$hasher.Dispose()}
$os=Get-CimInstance Win32_OperatingSystem
$root=(Get-Location).Path
$acl=Get-Acl -LiteralPath $root
$observations=[ordered]@{tcp='OBSERVED';udp='OBSERVED';gpu='OBSERVED'}
$tcpRows=@();$udpRows=@();$gpu=@()
try {$tcpRows=@(Get-NetTCPConnection -State Listen -ErrorAction Stop)}
catch {$observations.tcp='UNAVAILABLE'}
try {$udpRows=@(Get-NetUDPEndpoint -ErrorAction Stop)}
catch {$observations.udp='UNAVAILABLE'}
try {$gpu=@(Get-CimInstance Win32_VideoController -ErrorAction Stop | Select-Object Name,DriverVersion,AdapterRAM)}
catch {$observations.gpu='UNAVAILABLE'}
# Do not serialize exception text: it may contain private paths or provider data.
$ports=@($tcpRows | ForEach-Object {
    [ordered]@{port=$_.LocalPort;pid=$_.OwningProcess;scope=$(if($_.LocalAddress -in @('127.0.0.1','::1')){'loopback'}elseif($_.LocalAddress -in @('0.0.0.0','::')){'wildcard'}else{'interface-redacted'})}
})
$udp=@($udpRows | ForEach-Object {
    [ordered]@{port=$_.LocalPort;pid=$_.OwningProcess;scope=$(if($_.LocalAddress -in @('127.0.0.1','::1')){'loopback'}elseif($_.LocalAddress -in @('0.0.0.0','::')){'wildcard'}else{'interface-redacted'})}
})
[ordered]@{
    schema=1;phase='G0_READ_ONLY';captured_utc=(Get-Date).ToUniversalTime().ToString('o')
    node_name=$env:COMPUTERNAME;node_identity_sha256=$nodeHash
    os=$os | Select-Object Caption,Version,BuildNumber,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory
    cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
    disk=Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace
    services=Get-Service | ForEach-Object {[ordered]@{name=$_.Name;status=[string]$_.Status;start_type=[string]$_.StartType}}
    processes=Get-Process | Select-Object Id,ProcessName,WorkingSet64
    listeners=$ports
    udp_endpoints=$udp;gpu=$gpu;observations=$observations
    g0_readiness='BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE'
    unverified=[ordered]@{cuda_runtime='NOT_PROBED';python_dependencies='SEPARATE_PINNED_ENVIRONMENT_REQUIRED';process_db_ownership='OWNER_ATTESTATION_REQUIRED';target_identity='INDEPENDENT_VM_ATTESTATION_REQUIRED';ancestor_acl_namespace='NOT_PROVEN';resource_enforcement='NOT_PROVEN'}
    sandbox=[ordered]@{path=$root;reparse_point=[bool]((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint);acl_protected=$acl.AreAccessRulesProtected;acl_rule_count=$acl.Access.Count;confinement_proven=$false}
    secrets='No environment dump, command lines, connection strings, passwords or tokens collected'
    g1='NOT_AUTHORIZED'
} | ConvertTo-Json -Depth 7

