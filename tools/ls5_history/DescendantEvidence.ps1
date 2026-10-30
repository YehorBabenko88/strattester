function New-DescendantRecord {
 param($Edge,$Parent,$Observation)
 $r=[ordered]@{snapshot_pid=$Edge.Pid;snapshot_parent_pid=$Edge.ParentPid;pid=$Observation.pid;created=$Observation.created;parent_pid=$Observation.parent_pid;image=$Observation.image;session_id=$Observation.session_id;liveness=$Observation.liveness;cpu_seconds=$Observation.cpu_seconds;peak_ram_bytes=$Observation.peak_ram_bytes;exit_code=$Observation.exit_code;errors=@($Observation.errors);decision='REJECT';reason='UNEXPECTED_DESCENDANT';identity_admitted=$false;termination_authorized=$false;resource_scope='OBSERVATION_ONLY_NOT_ATTRIBUTED'}
 if($Observation.pid -ne $Edge.Pid -or $null -eq $Observation.created -or $null -eq $Observation.parent_pid){$r.reason='DESCENDANT_IDENTITY_INCOMPLETE'}
 elseif($Observation.parent_pid -ne $Edge.ParentPid -or $Edge.ParentPid -ne $Parent.Pid -or [long]$Observation.created -lt [long]$Parent.Created -or ($Parent.HasExited -and [long]$Observation.created -gt [long]$Parent.Exited)){$r.reason='DESCENDANT_PID_REUSE_OR_PARENT_MISMATCH'}
 elseif([string]::IsNullOrEmpty($Observation.image) -or $null -eq $Observation.session_id){$r.reason='DESCENDANT_IDENTITY_INCOMPLETE'}
 elseif($Observation.liveness -notin @('RUNNING','EXITED') -or $null -eq $Observation.cpu_seconds -or $null -eq $Observation.peak_ram_bytes -or @($Observation.errors).Count){$r.reason='DESCENDANT_METRICS_OR_STATE_UNVERIFIED'}
 return [pscustomobject]$r
}
function Write-DiagnosticEvidence {
 param([string]$Path,$Value)
 $data=[Text.Encoding]::UTF8.GetBytes(($Value|ConvertTo-Json -Depth 12))
 if($data.Length -gt 256KB){throw 'EVIDENCE_BOUND'}
 $dir=Split-Path $Path -Parent
 $used=[long]((Get-ChildItem -LiteralPath $dir -File|Where-Object Name -notin @('stdout.log','stderr.log')|Measure-Object Length -Sum).Sum)
 if($used+$data.Length -gt 512KB){throw 'TOTAL_EVIDENCE_BOUND'}
 $f=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
 try{$f.Write($data);$f.Flush($true)}finally{$f.Dispose()}
}

function Get-OwnedCleanupAction {
 param([string]$State)
 if($State -ceq 'EXITED'){return 'OBSERVE'}
 return 'STOP_OWNED_HANDLE'
}
