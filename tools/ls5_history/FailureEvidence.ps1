function Read-WorkerFailure {
 param([string]$Run,[int]$WorkerPid,[string]$Nonce,[string]$WorkerSha)
 $path=Join-Path $Run 'failure.json'
 if(-not (Test-Path -LiteralPath $path)){throw 'DIAGNOSTIC_INCOMPLETE'}
 $item=Get-Item -LiteralPath $path
 if($item.Length -gt 8192 -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'DIAGNOSTIC_INCOMPLETE'}
 $text=Get-Content -LiteralPath $path -Raw
 $doc=[Text.Json.JsonDocument]::Parse($text)
 function Check-FailureKeys($v){
  if($v.ValueKind -eq [Text.Json.JsonValueKind]::Object){$seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);foreach($property in $v.EnumerateObject()){if(-not $seen.Add($property.Name)){throw 'DIAGNOSTIC_INCOMPLETE'};Check-FailureKeys $property.Value}}
  elseif($v.ValueKind -eq [Text.Json.JsonValueKind]::Array){foreach($child in $v.EnumerateArray()){Check-FailureKeys $child}}
 }
 try{Check-FailureKeys $doc.RootElement}finally{$doc.Dispose()}
 $r=$text|ConvertFrom-Json -DateKind String
 if($r.schema -cne 'ls5.worker_failure.v1' -or $r.status -cne 'WORKER_FAILED' -or $r.pid -isnot [long] -and $r.pid -isnot [int] -or $r.pid -ne $WorkerPid -or $r.nonce -cne $Nonce -or $r.source.worker_sha256 -cne $WorkerSha -or $r.source.head -cne '11b6c793e6617c3de08e6ca4fa741625c54c1951' -or $r.source.tree -cne 'f3a7f9858a0ce59f425543b14e8c1d3593a1b8a9' -or $r.worker_exit_code -ne 2 -or $null -ne $r.controller_exit_code -or $r.controller_exit_code_status -cne 'NOT_YET_KNOWN'){throw 'DIAGNOSTIC_INCOMPLETE'}

 $fields=@('schema','status','phase','error_code','exception_type','pid','nonce','source','last_durable_marker','timestamp_utc','worker_exit_code','controller_exit_code','controller_exit_code_status','cpu_seconds','wall_seconds')
 if(@($r.PSObject.Properties).Count -ne $fields.Count -or @($r.PSObject.Properties.Name|Where-Object {$_ -cnotin $fields}).Count){throw 'DIAGNOSTIC_INCOMPLETE'}
 foreach($key in @('schema','status','phase','error_code','exception_type','nonce','timestamp_utc','controller_exit_code_status')){if($r.$key -isnot [string]){throw 'DIAGNOSTIC_INCOMPLETE'}}
 if(@($r.source.PSObject.Properties).Count -ne 3 -or @($r.source.PSObject.Properties.Name|Where-Object {$_ -cnotin @('head','tree','worker_sha256')}).Count){throw 'DIAGNOSTIC_INCOMPLETE'}
 foreach($key in @('head','tree','worker_sha256')){if($r.source.$key -isnot [string]){throw 'DIAGNOSTIC_INCOMPLETE'}}
 if($r.worker_exit_code -isnot [long] -and $r.worker_exit_code -isnot [int]){throw 'DIAGNOSTIC_INCOMPLETE'}
 foreach($n in @($r.cpu_seconds,$r.wall_seconds)){if(($n -isnot [int] -and $n -isnot [long] -and $n -isnot [double] -and $n -isnot [decimal]) -or -not [double]::IsFinite([double]$n) -or $n -lt 0){throw 'DIAGNOSTIC_INCOMPLETE'}}
 $stamp=[DateTimeOffset]::MinValue
 if(-not [DateTimeOffset]::TryParse($r.timestamp_utc,[ref]$stamp) -or $stamp.Offset -ne [TimeSpan]::Zero){throw 'DIAGNOSTIC_INCOMPLETE'}
 $map=Get-Content (Join-Path $PSScriptRoot 'PHASE_CODES.json') -Raw|ConvertFrom-Json
 if($r.phase -cnotin @($map.PSObject.Properties.Name) -or $r.error_code -cne $map.($r.phase)){throw 'DIAGNOSTIC_INCOMPLETE'}
 if($r.exception_type -cnotin @('ValueError','RuntimeError','AssertionError','OSError','PermissionError','FileNotFoundError','ImportError','ModuleNotFoundError','TypeError','KeyError','MemoryError','DatabaseError','OperationalError','IntegrityError','ProgrammingError','InterfaceError','DataError','NotSupportedError','OtherException')){throw 'DIAGNOSTIC_INCOMPLETE'}
 $journal=Join-Path $Run 'worker-markers.jsonl'
 if(Test-Path $journal){
  if((Get-Item $journal).Length -gt 32768){throw 'DIAGNOSTIC_INCOMPLETE'}
  if((Get-Item $journal).Length -gt 0){
   if($null -eq $r.last_durable_marker){throw 'DIAGNOSTIC_INCOMPLETE'}
   $rows=@(Read-StrictPythonwMarkers $journal -AllowPrefix);Assert-PythonwMarkers $rows $WorkerPid $Nonce -AllowPrefix
   $last=$rows[-1];$m=$r.last_durable_marker
   if(@($m.PSObject.Properties).Count -ne 6 -or @($m.PSObject.Properties.Name|Where-Object {$_ -cnotin @('seq','stage','pid','nonce','cpu_seconds','wall_seconds')}).Count){throw 'DIAGNOSTIC_INCOMPLETE'}
   if(($m.pid -isnot [int] -and $m.pid -isnot [long]) -or ($m.seq -isnot [int] -and $m.seq -isnot [long]) -or $m.stage -isnot [string] -or $m.nonce -isnot [string]){throw 'DIAGNOSTIC_INCOMPLETE'}
   foreach($n in @($m.cpu_seconds,$m.wall_seconds)){if(($n -isnot [int] -and $n -isnot [long] -and $n -isnot [double] -and $n -isnot [decimal]) -or -not [double]::IsFinite([double]$n)){throw 'DIAGNOSTIC_INCOMPLETE'}}
   foreach($key in @('seq','stage','pid','nonce','cpu_seconds','wall_seconds')){if($m.$key -cne $last.$key){throw 'DIAGNOSTIC_INCOMPLETE'}}
  }elseif($null -ne $r.last_durable_marker){throw 'DIAGNOSTIC_INCOMPLETE'}
 }elseif($null -ne $r.last_durable_marker){throw 'DIAGNOSTIC_INCOMPLETE'}
 return $r
}

