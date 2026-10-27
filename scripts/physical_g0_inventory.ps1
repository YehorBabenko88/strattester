# Read-only G0 metadata collector. No DB connections, process control, service
# mutations, installs, outbound requests, or filesystem writes. Emits JSON only.
$ErrorActionPreference='Stop'
$observations=[ordered]@{}
# Capture before publishing: a source that fails after yielding rows is unavailable,
# never a successful empty/partial inventory. Provider diagnostics are not evidence.
function Read-G0Source {
    param([string]$Name,[scriptblock]$Read,[string[]]$Required=@(),[bool]$AllowEmpty=$false)
    try {
        $rows=@(& $Read 3>$null 4>$null 5>$null 6>$null)
        $observations[$Name]='OBSERVED'
        if (!$AllowEmpty -and $rows.Count -eq 0) {$observations[$Name]='MISSING'}
        foreach($row in $rows) {
            foreach($field in $Required) {
                if ($null -eq $row.$field -or [string]::IsNullOrWhiteSpace([string]$row.$field)) {
                    $observations[$Name]='MISSING'
                }
            }
        }
        $rows
    }
    catch {$observations[$Name]='UNAVAILABLE'}
}
$node=@(Read-G0Source identity {Get-CimInstance Win32_ComputerSystemProduct} @('UUID'))
$nodeHash=$null
if ($observations.identity -eq 'OBSERVED') {
    $uuid=[string]$node[0].UUID
    $parsedUuid=[Guid]::Empty
    if (![Guid]::TryParse($uuid,[ref]$parsedUuid) -or [string]::IsNullOrWhiteSpace($env:COMPUTERNAME) -or $node.Count -ne 1 -or
        $parsedUuid -eq [Guid]::Empty -or $parsedUuid.ToString() -eq 'ffffffff-ffff-ffff-ffff-ffffffffffff') {
        $observations.identity='MISSING'
    } else {
        $identity=[System.Text.Encoding]::UTF8.GetBytes($env:COMPUTERNAME+'|'+$uuid)
        $hasher=[System.Security.Cryptography.SHA256]::Create()
        try {$nodeHash=([BitConverter]::ToString($hasher.ComputeHash($identity))).Replace('-','').ToLowerInvariant()}
        finally {$hasher.Dispose()}
    }
}
$os=@(Read-G0Source os {Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory} @('Caption','Version','BuildNumber','OSArchitecture','TotalVisibleMemorySize','FreePhysicalMemory'))
$cpu=@(Read-G0Source cpu {Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors} @('Name','NumberOfCores','NumberOfLogicalProcessors'))
$disk=@(Read-G0Source disk {Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace} @('DeviceID','Size','FreeSpace'))
$services=@(Read-G0Source services {Get-Service | ForEach-Object {
    [pscustomobject]@{name=$_.Name;status=[string]$_.Status;start_type=$(if($null -ne $_.StartType){[string]$_.StartType}else{$null})}
}} @('name','status','start_type'))
$processes=@(Read-G0Source processes {Get-Process | Select-Object Id,ProcessName,WorkingSet64} @('Id','ProcessName','WorkingSet64'))
$tcpRows=@(Read-G0Source tcp {Get-NetTCPConnection -State Listen -ErrorAction Stop} @('LocalPort','OwningProcess','LocalAddress') $true)
$udpRows=@(Read-G0Source udp {Get-NetUDPEndpoint -ErrorAction Stop} @('LocalPort','OwningProcess','LocalAddress') $true)
$gpu=@(Read-G0Source gpu {Get-CimInstance Win32_VideoController -ErrorAction Stop | Select-Object Name,DriverVersion,AdapterRAM} @('Name','DriverVersion','AdapterRAM'))
$sandbox=@(Read-G0Source sandbox {
    $root=(Get-Location).Path
    $acl=Get-Acl -LiteralPath $root
    $item=Get-Item -LiteralPath $root
    [pscustomobject]@{path=$root;reparse_point=$(if($null -ne $item.Attributes){[bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)}else{$null});acl_protected=$acl.AreAccessRulesProtected;acl_rule_count=$(if($null -ne $acl.Access){@($acl.Access).Count}else{$null});confinement_proven=$false}
} @('path','reparse_point','acl_protected','acl_rule_count'))
$ports=@($tcpRows | ForEach-Object {
    [ordered]@{port=$_.LocalPort;pid=$_.OwningProcess;scope=$(if($_.LocalAddress -in @('127.0.0.1','::1')){'loopback'}elseif($_.LocalAddress -in @('0.0.0.0','::')){'wildcard'}else{'interface-redacted'})}
})
$udp=@($udpRows | ForEach-Object {
    [ordered]@{port=$_.LocalPort;pid=$_.OwningProcess;scope=$(if($_.LocalAddress -in @('127.0.0.1','::1')){'loopback'}elseif($_.LocalAddress -in @('0.0.0.0','::')){'wildcard'}else{'interface-redacted'})}
})
[ordered]@{
    schema=1;phase='G0_READ_ONLY';captured_utc=(Get-Date).ToUniversalTime().ToString('o')
    node_name=$env:COMPUTERNAME;node_identity_sha256=$nodeHash
    os=$(if($os.Count -eq 1){$os[0]}else{$null})
    cpu=$cpu;disk=$disk;services=$services;processes=$processes
    listeners=$ports;udp_endpoints=$udp;gpu=$gpu;observations=$observations
    g0_readiness='BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE'
    unverified=[ordered]@{cuda_runtime='NOT_PROBED';python_dependencies='SEPARATE_PINNED_ENVIRONMENT_REQUIRED';process_db_ownership='OWNER_ATTESTATION_REQUIRED';target_identity='INDEPENDENT_VM_ATTESTATION_REQUIRED';ancestor_acl_namespace='NOT_PROVEN';resource_enforcement='NOT_PROVEN'}
    sandbox=$(if($sandbox.Count -eq 1){$sandbox[0]}else{$null})
    secrets='No environment dump, command lines, connection strings, passwords or tokens collected'
    g1='NOT_AUTHORIZED'
} | ConvertTo-Json -Depth 7
