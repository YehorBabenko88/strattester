param(
 [string]$Inventory="$PSScriptRoot\cluster-nodes.example.json",
 [string]$IdentityFile="$env:USERPROFILE\.ssh\strattester_control_ed25519",
 [int]$ConnectTimeoutSeconds=3
)
$ErrorActionPreference='Stop'
function Read-PlainSecret([string]$Prompt){
 $s=Read-Host $Prompt -AsSecureString
 $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
 try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)}
 finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)}
}
$userPassword=Read-PlainSecret "PostgreSQL password for role 'user'"
$postgresPassword=Read-PlainSecret "PostgreSQL password for role 'postgres'"
$probe=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$InformationPreference='SilentlyContinue'
$inputData=[Console]::In.ReadToEnd()|ConvertFrom-Json
$psql=$null;$c=Get-Command psql.exe -EA SilentlyContinue;if($c){$psql=$c.Source}
if(!$psql){$x=@(Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -EA SilentlyContinue|Sort-Object FullName -Descending);if($x){$psql=$x[0].FullName}}
if(!$psql){[pscustomobject]@{Hostname=(hostname);Role=$inputData.Role;Status='PSQL_NOT_FOUND';Databases=@()}|ConvertTo-Json -Depth 8 -Compress;exit}
$oldP=$env:PGPASSWORD;$oldT=$env:PGCONNECT_TIMEOUT
try{
 $env:PGPASSWORD=$inputData.Password;$env:PGCONNECT_TIMEOUT=[string]$inputData.Timeout
 $dbNames=@(& $psql -w -U $inputData.Role -d postgres -Atc "select datname from pg_database where datistemplate=false and datname in ('trading_bot','bybit_flow') order by 1" 2>$null)
 if($LASTEXITCODE -ne 0){[pscustomobject]@{Hostname=(hostname);Role=$inputData.Role;Status='AUTH_OR_CONNECT_FAILED';Databases=@()}|ConvertTo-Json -Depth 8 -Compress;exit}
 $items=@()
 foreach($db in $dbNames){
  $sizeRaw=@(& $psql -w -U $inputData.Role -d postgres -Atc "select pg_database_size('$db')" 2>$null)
  $connRaw=@(& $psql -w -U $inputData.Role -d postgres -Atc "select count(*) from pg_stat_activity where datname='$db'" 2>$null)
  $schemaRaw=@(& $psql -w -U $inputData.Role -d $db -Atc "select schema_name from information_schema.schemata where schema_name not in ('pg_catalog','information_schema') and schema_name not like 'pg_toast%' order by 1" 2>$null)
  $tableRaw=@(& $psql -w -U $inputData.Role -d $db -Atc "select schemaname||'.'||tablename from pg_tables where schemaname not in ('pg_catalog','information_schema') order by 1 limit 200" 2>$null)
  $tableCountRaw=@(& $psql -w -U $inputData.Role -d $db -Atc "select count(*) from pg_tables where schemaname not in ('pg_catalog','information_schema')" 2>$null)
  $items+=[pscustomobject]@{
   Name=$db
   SizeBytes=if($sizeRaw){[int64]$sizeRaw[0]}else{$null}
   Connections=if($connRaw){[int]$connRaw[0]}else{$null}
   Schemas=@($schemaRaw)
   TableCount=if($tableCountRaw){[int]$tableCountRaw[0]}else{$null}
   Tables=@($tableRaw)
  }
 }
 [pscustomobject]@{Hostname=(hostname);Role=$inputData.Role;Status='OK';Databases=$items}|ConvertTo-Json -Depth 8 -Compress
} finally {$env:PGPASSWORD=$oldP;$env:PGCONNECT_TIMEOUT=$oldT}
'@
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe))
$nodes=(Get-Content $Inventory -Raw|ConvertFrom-Json).nodes
foreach($n in $nodes){
 Write-Host "=== $($n.id) ==="
 foreach($entry in @(@{Role='user';Password=$userPassword},@{Role='postgres';Password=$postgresPassword})){
  $inputJson=[pscustomobject]@{Role=$entry.Role;Password=$entry.Password;Timeout=$ConnectTimeoutSeconds}|ConvertTo-Json -Compress
  if($n.local){$inputJson|powershell.exe -NoProfile -NonInteractive -EncodedCommand $encoded}
  else{$inputJson|ssh -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=8 -i $IdentityFile "$($n.user)@$($n.ssh_host)" "powershell.exe -NoProfile -NonInteractive -EncodedCommand $encoded"}
 }
}
$userPassword=$null;$postgresPassword=$null
