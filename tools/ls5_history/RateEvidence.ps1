function Test-PublicRateLedger {
 param([string]$Run,[int]$WorkerPid,[string]$Nonce)
 $failed=[ordered]@{status='RATE_BUDGET_FAIL';reason='MISSING_OR_INVALID_EVIDENCE';budget_limit=20}
 try{
  $path=Join-Path $Run 'rate-events.jsonl';$requests=Join-Path $Run 'requests.jsonl'
  if(-not (Test-Path $path) -or -not (Test-Path $requests) -or (Get-Item $path).Length -gt 65536 -or (Get-Item $requests).Length -gt 262144){return [pscustomobject]$failed}
  $required=@('sequence','endpoint_id','attempt_start_ns','http_start_ns','completed_ns','duration_ns','http_status','budget_used','budget_limit','pid','nonce','utc_start')
  function Read-RateRows($File,$Fields){
   @(Get-Content -LiteralPath $File|ForEach-Object {
    $doc=[Text.Json.JsonDocument]::Parse($_)
    try{
     if($doc.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::Object){throw 'RATE_FIELDS'}
     $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
     foreach($property in $doc.RootElement.EnumerateObject()){if($property.Name -cnotin $Fields -or -not $seen.Add($property.Name)){throw 'RATE_FIELDS'}}
     if($seen.Count -ne $Fields.Count){throw 'RATE_FIELDS'}
    }finally{$doc.Dispose()}
    $_|ConvertFrom-Json -DateKind String
   })
  }
  $startPath=Join-Path $Run 'rate-starts.jsonl'
  if(-not (Test-Path $startPath) -or (Get-Item $startPath).Length -gt 65536){return [pscustomobject]$failed}
  $startKeys=@('sequence','endpoint_id','attempt_start_ns','utc_start','budget_used','budget_limit','pid','nonce')
  $events=@(Read-RateRows $path $required);$starts=@(Read-RateRows $startPath $startKeys);
$used=@(Get-Content -LiteralPath $requests).Count
  if($used -lt 1 -or $used -gt 20 -or $events.Count -ne $used -or $starts.Count -ne $used){return [pscustomobject]$failed}
  $attempts=[Collections.Generic.List[long]]::new();$sends=[Collections.Generic.List[long]]::new()
  for($i=0;$i -lt $events.Count;$i++){
   $e=$events[$i];$start=$starts[$i]
   foreach($key in $startKeys){if($null -eq $start.$key -or $start.$key.GetType() -ne $e.$key.GetType() -or $start.$key -cne $e.$key){return [pscustomobject]$failed}}
   if($e.nonce -isnot [string] -or $e.endpoint_id -isnot [string]){return [pscustomobject]$failed}
   foreach($key in @('sequence','attempt_start_ns','completed_ns','duration_ns','budget_used','budget_limit','pid')){if($e.$key -isnot [int] -and $e.$key -isnot [long]){return [pscustomobject]$failed}}
   if($e.sequence -ne $i+1 -or $e.pid -ne $WorkerPid -or $e.nonce -cne $Nonce -or $e.endpoint_id -cnotin @('time','instruments','kline') -or $e.budget_limit -ne 20 -or $e.budget_used -ne $i+1 -or $e.attempt_start_ns -lt 0 -or $e.completed_ns -lt $e.attempt_start_ns -or $e.duration_ns -ne $e.completed_ns-$e.attempt_start_ns){return [pscustomobject]$failed}
   $stamp=[DateTimeOffset]::MinValue
   if($e.utc_start -isnot [string] -or -not [DateTimeOffset]::TryParse($e.utc_start,[ref]$stamp) -or $stamp.Offset -ne [TimeSpan]::Zero){return [pscustomobject]$failed}
   if($null -ne $e.http_status -and (($e.http_status -isnot [int] -and $e.http_status -isnot [long]) -or $e.http_status -lt 100 -or $e.http_status -gt 599)){return [pscustomobject]$failed}
   $attempts.Add([long]$e.attempt_start_ns)
   if($null -ne $e.http_start_ns){
    if(($e.http_start_ns -isnot [int] -and $e.http_start_ns -isnot [long]) -or $e.http_start_ns -lt $e.attempt_start_ns -or $e.http_start_ns -gt $e.completed_ns){return [pscustomobject]$failed}
    $sends.Add([long]$e.http_start_ns)
   }elseif($null -ne $e.http_status){return [pscustomobject]$failed}
  }
  foreach($series in @($attempts,$sends)){
   for($i=1;$i -lt $series.Count;$i++){if($series[$i] -lt $series[$i-1]){return [pscustomobject]$failed}}
   for($i=2;$i -lt $series.Count;$i++){if($series[$i]-$series[$i-2] -le 1000000000L){$failed.reason='SLIDING_WINDOW';return [pscustomobject]$failed}}
  }
  return [pscustomobject]@{status='RATE_BUDGET_PASS';budget_used=$used;budget_remaining=20-$used;budget_limit=20;http_starts_verified=$sends.Count;attempts_verified=$attempts.Count;verifier='INDEPENDENT_POWERSHELL_POSTRUN'}
 }catch{return [pscustomobject]$failed}
}
