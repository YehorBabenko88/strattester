function Assert-PythonwMarkers {
 param([object[]]$Rows,[int]$PidValue,[string]$Nonce,[switch]$AllowPrefix)
 $expected=@(Get-Content (Join-Path $PSScriptRoot 'EXPECTED_MARKERS.json') -Raw|ConvertFrom-Json)
 if(($AllowPrefix -and ($Rows.Count -lt 1 -or $Rows.Count -gt $expected.Count)) -or (-not $AllowPrefix -and $Rows.Count -ne $expected.Count)){throw 'MARKERS_INCOMPLETE'}
 $lastCpu=-1.0;$lastWall=-1.0
 for($i=0;$i -lt $Rows.Count;$i++){
  $r=$Rows[$i]
  if(($r.seq -isnot [int] -and $r.seq -isnot [long]) -or ($r.pid -isnot [int] -and $r.pid -isnot [long]) -or $r.stage -isnot [string] -or $r.nonce -isnot [string]){throw 'MARKER_FIELD_TYPES'}
  if($r.seq -ne ($i+1) -or $r.stage -cne $expected[$i] -or $r.pid -ne $PidValue -or $r.nonce -cne $Nonce){throw 'MARKER_BINDING_OR_ORDER'}
  foreach($n in @($r.cpu_seconds,$r.wall_seconds)){if($null -eq $n -or ($n -isnot [int] -and $n -isnot [long] -and $n -isnot [double] -and $n -isnot [decimal]) -or -not [double]::IsFinite([double]$n) -or [double]$n -lt 0){throw 'MARKER_METRICS'}}
  if($r.cpu_seconds -lt $lastCpu -or $r.wall_seconds -lt $lastWall){throw 'MARKER_TIME_REVERSAL'}
  $lastCpu=$r.cpu_seconds;$lastWall=$r.wall_seconds
 }
}
function Assert-PrivateRunPath {
 param([string]$Run)
 $node=Split-Path $Run -Parent
 while($node){$item=Get-Item -LiteralPath $node -ErrorAction Stop;if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'LINKED_RUN_PATH'};$parent=Split-Path $node -Parent;if($parent -eq $node){break};$node=$parent}
}
function Read-StrictPythonwMarkers {
 param([string]$Path,[switch]$AllowPrefix)
 $lines=@(Get-Content -LiteralPath $Path)
 $count=@(Get-Content (Join-Path $PSScriptRoot 'EXPECTED_MARKERS.json') -Raw|ConvertFrom-Json).Count
 if(($AllowPrefix -and ($lines.Count -lt 1 -or $lines.Count -gt $count)) -or (-not $AllowPrefix -and $lines.Count -ne $count)){throw 'MARKER_LINE_COUNT'}
 foreach($line in $lines){
  $doc=[Text.Json.JsonDocument]::Parse($line)
  try{
   if($doc.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::Object){throw 'MARKER_NOT_OBJECT'}
   $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
   foreach($property in $doc.RootElement.EnumerateObject()){
    if($property.Name -cnotin @('seq','stage','pid','nonce','cpu_seconds','wall_seconds') -or -not $seen.Add($property.Name)){throw 'MARKER_DUPLICATE_OR_UNKNOWN_KEY'}
   }
   if($seen.Count -ne 6){throw 'MARKER_FIELDS_MISSING'}
   foreach($key in @('seq','pid')){$v=$doc.RootElement.GetProperty($key);$number=0L;if($v.ValueKind -ne [Text.Json.JsonValueKind]::Number -or -not $v.TryGetInt64([ref]$number)){throw 'MARKER_INTEGER_TYPE'}}
   foreach($key in @('stage','nonce')){if($doc.RootElement.GetProperty($key).ValueKind -ne [Text.Json.JsonValueKind]::String){throw 'MARKER_STRING_TYPE'}}
   foreach($key in @('cpu_seconds','wall_seconds')){if($doc.RootElement.GetProperty($key).ValueKind -ne [Text.Json.JsonValueKind]::Number){throw 'MARKER_NUMBER_TYPE'}}
  }finally{$doc.Dispose()}
  $line|ConvertFrom-Json
 }
}
