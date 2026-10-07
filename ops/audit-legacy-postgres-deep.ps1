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
$postgresPassword=Read-PlainSecret "PostgreSQL password for role 'postgres'"
$probe=@'
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$InformationPreference='SilentlyContinue'
$inputData=[Console]::In.ReadToEnd()|ConvertFrom-Json
$psql=$null;$c=Get-Command psql.exe -EA SilentlyContinue;if($c){$psql=$c.Source}
if(!$psql){$x=@(Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -EA SilentlyContinue|Sort-Object FullName -Descending);if($x){$psql=$x[0].FullName}}
if(!$psql){[pscustomobject]@{Hostname=(hostname);Status='PSQL_NOT_FOUND';Databases=@()}|ConvertTo-Json -Depth 10 -Compress;exit}
$oldP=$env:PGPASSWORD;$oldT=$env:PGCONNECT_TIMEOUT
try{
 $env:PGPASSWORD=$inputData.Password;$env:PGCONNECT_TIMEOUT=[string]$inputData.Timeout
 $dbNames=@(& $psql -w -U postgres -d postgres -Atc "select datname from pg_database where datistemplate=false and datname in ('trading_bot','bybit_flow') order by 1" 2>$null)
 if($LASTEXITCODE -ne 0){[pscustomobject]@{Hostname=(hostname);Status='AUTH_OR_CONNECT_FAILED';Databases=@()}|ConvertTo-Json -Depth 10 -Compress;exit}
 $dbs=@()
 foreach($db in $dbNames){
  $size=@(& $psql -w -U postgres -d postgres -Atc "select pg_database_size('$db')" 2>$null)
  $conns=@(& $psql -w -U postgres -d postgres -Atc "select count(*) from pg_stat_activity where datname='$db'" 2>$null)
  $extensions=@(& $psql -w -U postgres -d $db -Atc "select extname||':'||extversion from pg_extension order by 1" 2>$null)
  $views=@(& $psql -w -U postgres -d $db -Atc "select schemaname||'.'||viewname from pg_views where schemaname not in ('pg_catalog','information_schema') order by 1" 2>$null)
  $matviews=@(& $psql -w -U postgres -d $db -Atc "select schemaname||'.'||matviewname from pg_matviews where schemaname not in ('pg_catalog','information_schema') order by 1" 2>$null)
  $seqCount=@(& $psql -w -U postgres -d $db -Atc "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.relkind='S' and n.nspname not in ('pg_catalog','information_schema')" 2>$null)
  $funcCount=@(& $psql -w -U postgres -d $db -Atc "select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname not in ('pg_catalog','information_schema')" 2>$null)
  $topRaw=@(& $psql -w -U postgres -d $db -Atc "select n.nspname||'.'||c.relname||'|'||pg_total_relation_size(c.oid)||'|'||greatest(c.reltuples::bigint,0) from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.relkind='r' and n.nspname not in ('pg_catalog','information_schema') order by pg_total_relation_size(c.oid) desc limit 30" 2>$null)
  $top=@()
  foreach($line in $topRaw){
   $parts=$line -split '\|',3
   if($parts.Count -eq 3){$top+=[pscustomobject]@{Table=$parts[0];TotalBytes=[int64]$parts[1];EstimatedRows=[int64]$parts[2]}}
  }
  $dbs+=[pscustomobject]@{
   Name=$db
   SizeBytes=if($size){[int64]$size[0]}else{$null}
   Connections=if($conns){[int]$conns[0]}else{$null}
   Extensions=@($extensions)
   Views=@($views)
   MaterializedViews=@($matviews)
   SequenceCount=if($seqCount){[int]$seqCount[0]}else{$null}
   FunctionCount=if($funcCount){[int]$funcCount[0]}else{$null}
   LargestTables=$top
  }
 }
 [pscustomobject]@{Hostname=(hostname);Status='OK';Databases=$dbs}|ConvertTo-Json -Depth 10 -Compress
} finally {$env:PGPASSWORD=$oldP;$env:PGCONNECT_TIMEOUT=$oldT}
'@
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe))
$nodes=(Get-Content $Inventory -Raw|ConvertFrom-Json).nodes
foreach($n in $nodes){
 Write-Host "=== $($n.id) ==="
 $inputJson=[pscustomobject]@{Password=$postgresPassword;Timeout=$ConnectTimeoutSeconds}|ConvertTo-Json -Compress
 if($n.local){$inputJson|powershell.exe -NoProfile -NonInteractive -EncodedCommand $encoded}
 else{$inputJson|ssh -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=8 -i $IdentityFile "$($n.user)@$($n.ssh_host)" "powershell.exe -NoProfile -NonInteractive -EncodedCommand $encoded"}
}
$postgresPassword=$null
