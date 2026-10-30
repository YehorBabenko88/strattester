$ErrorActionPreference='Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'DescendantEvidence.ps1')
$p=[pscustomobject]@{Pid=10;Created='100';HasExited=$false;Exited=$null}
$edge=[pscustomobject]@{Pid=11;ParentPid=10}
$good=[pscustomobject]@{pid=11;parent_pid=10;created='101';image='C:\fixture\unknown.exe';session_id=1;liveness='RUNNING';cpu_seconds=0.01;peak_ram_bytes=4096;errors=@()}
$r=New-DescendantRecord $edge $p $good
if($r.decision -cne 'REJECT' -or $r.reason -cne 'UNEXPECTED_DESCENDANT' -or $r.image -cne $good.image){throw 'IDENTITY_LOST_OR_ACCEPTED'}
foreach($mode in @('PID_REUSE','MISSING_IMAGE','EXIT_BEFORE_INSPECTION','MISSING_METRICS','MISSING_PARENT','UNKNOWN')){
 $v=$good.PSObject.Copy()
 switch($mode){
 'PID_REUSE'{$v.created='99'}
 'MISSING_IMAGE'{$v.image=$null}
 'EXIT_BEFORE_INSPECTION'{$v=[pscustomobject]@{pid=11;errors=@('OPEN_FAILED')}}
 'MISSING_METRICS'{$v.cpu_seconds=$null}
 'MISSING_PARENT'{$v.parent_pid=$null}
 'UNKNOWN'{$v.liveness='UNKNOWN'}
 }
 $r=New-DescendantRecord $edge $p $v
 if($r.decision -cne 'REJECT' -or $r.snapshot_pid -ne 11 -or $r.reason -ceq 'UNEXPECTED_DESCENDANT'){throw ('BAD_NEGATIVE_'+$mode)}
}
'7_DESCENDANT_FIXTURES_PASS_NO_NATIVE_CALLS'

foreach($state in @('RUNNING','UNKNOWN','INVALID')){if((Get-OwnedCleanupAction $state) -cne 'STOP_OWNED_HANDLE'){throw 'METRIC_FAILURE_SUPPRESSES_CLEANUP'}};if((Get-OwnedCleanupAction 'EXITED') -cne 'OBSERVE'){throw 'EXITED_CLEANUP'}
'4_CLEANUP_DECISION_FIXTURES_PASS'

