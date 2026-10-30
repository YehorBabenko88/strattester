param([switch]$Execute,[ValidateRange(1,16)][int]$BatchIndex=1,[string]$PreviousCheckpointSha256='',[string]$PreviousControllerSha256='')
if(-not $Execute){'PREPARATION_ONLY_EXECUTION_NOT_AUTHORIZED';exit 0}
$ErrorActionPreference='Stop'
if([Environment]::MachineName -ne 'LS5' -or [Environment]::UserName -ne 'LS-5' -or $PSVersionTable.PSVersion -ne [version]'7.6.5'){throw 'TARGET_IDENTITY'}
$packageRoot=[IO.Path]::GetFullPath($PSScriptRoot)+[IO.Path]::DirectorySeparatorChar
foreach($r in (Get-Content (Join-Path $PSScriptRoot 'MANIFEST.json') -Raw|ConvertFrom-Json)){
 if($r.file -notmatch '^[A-Za-z0-9_./-]+$' -or [IO.Path]::IsPathRooted($r.file) -or @($r.file.Split('/')|Where-Object {$_ -in @('','..','.')}).Count){throw 'PACKAGE_PATH'}
 $inputFile=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $r.file))
 if(-not $inputFile.StartsWith($packageRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'PACKAGE_ESCAPE'}
 $node=$inputFile
 while($node -and $node -ne $PSScriptRoot){if((Get-Item -LiteralPath $node).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'PACKAGE_REPARSE'};$node=Split-Path $node -Parent}
 if((Get-Item -LiteralPath $inputFile).Length -ne $r.bytes -or (Get-FileHash -LiteralPath $inputFile).Hash -ine $r.sha256){throw 'PACKAGE_SHA'}
}
$python='C:\Users\LS-5\AppData\Local\Python\pythoncore-3.12-64\pythonw.exe'
if((Get-FileHash $python).Hash -ine 'd72294fb338bc2fc8896d25a7395a4db466425427e1559e77185d5135a830681'){throw 'PYTHON_SHA'}
if((Get-FileHash (Join-Path (Split-Path $python) 'python312.dll')).Hash -ine '9a0e3435aaa680d868150f87ab3e388ad2eebc22f87e036155c7b4eda8cd2120'){throw 'PYTHON_DLL_SHA'}
Add-Type -Path (Join-Path $PSScriptRoot 'DescendantCapture.cs');. (Join-Path $PSScriptRoot 'DescendantEvidence.ps1');. (Join-Path $PSScriptRoot 'PythonwEvidence.ps1');. (Join-Path $PSScriptRoot 'FailureEvidence.ps1');. (Join-Path $PSScriptRoot 'RateEvidence.ps1');Add-Type -Path (Join-Path $PSScriptRoot 'ProcessFamily.cs');Add-Type -Path (Join-Path $PSScriptRoot 'OutputCapture.cs')
$session='C:\Users\LS-5\Strattester-Physical-Test\DataFirst-11b6c79\F1-History-11b6c79'
$run=Join-Path $session ('attempt-'+$BatchIndex.ToString('0000'))
$dataBatch=Join-Path $session ('batch-'+$BatchIndex.ToString('0000'))
if($BatchIndex -gt 1 -and ($PreviousCheckpointSha256 -notmatch '^[a-f0-9]{64}$' -or $PreviousControllerSha256 -notmatch '^[a-f0-9]{64}$')){throw 'EXTERNAL_PREDECESSOR_PINS_REQUIRED'}
if($BatchIndex -eq 1 -and ($PreviousCheckpointSha256 -or $PreviousControllerSha256)){throw 'INITIAL_PREDECESSOR'}
if(-not (Test-Path $session)){Assert-PrivateRunPath $session;[void][IO.Directory]::CreateDirectory($session)}
if(Test-Path $run){throw 'EXISTING_ATTEMPT_NO_RETRY'}
Assert-PrivateRunPath $run
[void][IO.Directory]::CreateDirectory($run)
Write-DiagnosticEvidence (Join-Path $run 'batch-config.json') @{batch_index=$BatchIndex;previous_checkpoint_sha256=if($BatchIndex -gt 1){$PreviousCheckpointSha256}else{$null};previous_controller_sha256=if($BatchIndex -gt 1){$PreviousControllerSha256}else{$null}}
$nonce=[Guid]::NewGuid().ToString('N')
# Only newly created controller logs may exist at worker admission.
$watch=[Diagnostics.Stopwatch]::StartNew();$child=[Diagnostics.Process]::new();$handle=$null;$started=$false;$identity=$null;$final=$null;$status='RESOURCE_UNVERIFIED';$detail='UNFINISHED';$workerFailure=$null;$rateBudget=$null;$diagnosticStatus='NOT_APPLICABLE';$markersValidated=$false;$descendants=@();$controllerExit=2;$observedChild=$false;$out=$null;$err=$null;$stdoutTask=$null;$stderrTask=$null;$budget=[ResearchOutputCapture+Budget]::new()
try{
 $psi=[Diagnostics.ProcessStartInfo]::new();$psi.FileName=$python;$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
 foreach($a in @('-I','-S','-B',(Join-Path $PSScriptRoot 'worker.py'),$run,$nonce)){$psi.ArgumentList.Add($a)}
 $psi.Environment.Clear();$psi.Environment['SystemRoot']=$env:SystemRoot;$psi.Environment['TEMP']=$run;$psi.Environment['TMP']=$run;$child.StartInfo=$psi
 $out=[IO.File]::Open((Join-Path $run 'stdout.log'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);$err=[IO.File]::Open((Join-Path $run 'stderr.log'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
 $started=$child.Start();if(-not $started){throw 'LAUNCH_FAILED'};$handle=$child.SafeHandle
 $identity=[ResearchProcessFamily]::Read($handle.DangerousGetHandle())
 if($identity.Pid -ne $child.Id -or $identity.Image -ine $python -or $identity.Liveness -cne 'RUNNING'){throw 'WORKER_IDENTITY'}
 $stdoutTask=[ResearchOutputCapture]::Pump($child.StandardOutput.BaseStream,$out,$budget);$stderrTask=[ResearchOutputCapture]::Pump($child.StandardError.BaseStream,$err,$budget)
 while($true){
  $sample=[ResearchProcessFamily]::Read($handle.DangerousGetHandle(),$false)
  if($sample.Pid -ne $identity.Pid -or $sample.Created -cne $identity.Created){throw 'IDENTITY_CHANGED'}
  $edges=@([ResearchProcessFamily]::Snapshot()|Where-Object ParentPid -eq $identity.Pid)
  if($edges.Count){
   $observedChild=$true
   Write-DiagnosticEvidence (Join-Path $run 'unexpected-snapshot.json') @($edges|Select-Object -First 16|ForEach-Object {@{pid=$_.Pid;parent_pid=$_.ParentPid;state='NOT_INSPECTED';reason='UNEXPECTED_DESCENDANT';created=$null;image=$null;session_id=$null}})
   foreach($edge in ($edges|Select-Object -First 16)){
    try{$observation=[DescendantCapture]::Inspect([uint32]$edge.Pid)}catch{$observation=[pscustomobject]@{pid=$edge.Pid;liveness='UNKNOWN';errors=@('INSPECTION_EXCEPTION')}}
    $descendants+=New-DescendantRecord $edge $identity $observation
   }
   Write-DiagnosticEvidence (Join-Path $run 'unexpected-descendants.json') $descendants
   throw 'UNEXPECTED_DESCENDANT'
  }
  if($budget.Exceeded){throw 'OUTPUT_LIMIT'}
  if([long]((Get-ChildItem @($run,$dataBatch) -File -Recurse -ErrorAction SilentlyContinue|Measure-Object Length -Sum).Sum) -gt 127MB){throw 'TOTAL_ARTIFACT_BOUND'}
  if([long]((Get-ChildItem $session -File -Recurse|Measure-Object Length -Sum).Sum) -gt 2GB){throw 'SESSION_DISK_LIMIT'}
  if($sample.CpuSeconds -gt 15 -or $sample.PeakBytes -gt 512MB -or $watch.Elapsed.TotalSeconds -gt 90){throw 'RESOURCE_LIMIT'}
  if($sample.Liveness -ceq 'EXITED'){$final=$sample;break}
  Start-Sleep -Milliseconds 20
 }
 if(-not $stdoutTask.Wait(2000) -or -not $stderrTask.Wait(2000)){throw 'OUTPUT_UNVERIFIED'}
 [void]$stdoutTask.GetAwaiter().GetResult();[void]$stderrTask.GetAwaiter().GetResult();$out.Flush($true);$err.Flush($true)
 $stdout=Get-Content (Join-Path $run 'stdout.log') -Raw;$stderr=Get-Content (Join-Path $run 'stderr.log') -Raw
 if($null -eq $stdout){$stdout=''};if($null -eq $stderr){$stderr=''}
 if([Text.Encoding]::UTF8.GetByteCount($stdout)+[Text.Encoding]::UTF8.GetByteCount($stderr) -gt 1MB){throw 'OUTPUT_LIMIT'}
 if($final.ExitCode -ne 0){
  $diagnosticStatus='DIAGNOSTIC_INCOMPLETE'
  if($final.ExitCode -eq 2){
   try{$workerFailure=Read-WorkerFailure $run $identity.Pid $nonce ((Get-FileHash (Join-Path $PSScriptRoot 'worker.py')).Hash.ToLowerInvariant());$diagnosticStatus='FAILURE_RECEIPT_VERIFIED'}catch{throw 'DIAGNOSTIC_INCOMPLETE'}
  }else{throw 'DIAGNOSTIC_INCOMPLETE'}
  throw 'WORKER_FAILED'
 }
 if($stderr.Length){throw 'UNEXPECTED_STDERR'}
 if(Test-Path (Join-Path $run 'failure.json')){throw 'FAILURE_RECEIPT_WITH_ZERO_EXIT'}
 $markerPath=Join-Path $run 'worker-markers.jsonl'
 if(-not (Test-Path -LiteralPath $markerPath) -or (Get-Item -LiteralPath $markerPath).Length -gt 32768){throw 'MARKERS_MISSING_OR_BOUND'}
 $rows=@(Read-StrictPythonwMarkers $markerPath)
 Assert-PythonwMarkers $rows $identity.Pid $nonce
 $markersValidated=$true
 $resultPath=Join-Path $run 'result.json'
 if(-not (Test-Path $resultPath) -or (Get-Item $resultPath).Length -gt 6MB){throw 'RESULT_MISSING_OR_BOUND'}
 $result=Get-Content $resultPath -Raw|ConvertFrom-Json
 $hashPin=Get-Content (Join-Path $run 'result-sha256.json') -Raw|ConvertFrom-Json
 if((Get-FileHash $resultPath).Hash -ine $hashPin.sha256){throw 'RESULT_HASH'}
 if($result.nonce -cne $nonce -or $result.pid -ne $identity.Pid -or $result.status -cne 'F1_BATCH_VERIFIED' -or $result.batch_index -ne $BatchIndex -or $result.history_state -cnotin @('PARTIAL','READY') -or $result.requests -gt 20 -or $result.strategies -cne 'NOT_EXECUTED' -or $result.rate_budget.status -cne 'RATE_BUDGET_PASS' -or (Get-FileHash (Join-Path $dataBatch 'checkpoint.json')).Hash -ine $result.checkpoint_sha256){throw 'F1_RESULT_BINDING'}
 $status='F1_BATCH_VERIFIED' ;$detail=$null
}catch{$detail='RESOURCE_UNVERIFIED';if($_.Exception.Message -cmatch '^[A-Z_]+$'){$detail=$_.Exception.Message}}
finally{
 $primaryDetail=$detail
 # Cleanup is independent of accounting: only the retained handle returned by our own Start.
 if($started -and $handle){
  try{$state=[DescendantCapture]::OwnedLiveness($handle.DangerousGetHandle());if((Get-OwnedCleanupAction $state) -ceq 'STOP_OWNED_HANDLE'){[ResearchProcessFamily]::Stop($handle.DangerousGetHandle());if(-not $child.WaitForExit(2000)){throw 'OWNED_STOP_TIMEOUT'}}}catch{$status='RESOURCE_UNVERIFIED';$detail='OWNED_CLEANUP_UNVERIFIED'}
  try{$final=[ResearchProcessFamily]::Read($handle.DangerousGetHandle(),$false);if($final.Liveness -cne 'EXITED'){throw 'FINAL_METRICS'}}catch{$status='RESOURCE_UNVERIFIED';$detail='FINAL_METRICS_UNVERIFIED'}
 }

 foreach($task in @($stdoutTask,$stderrTask)){if($task){try{if(-not $task.Wait(2000)){throw 'DRAIN_TIMEOUT'};[void]$task.GetAwaiter().GetResult()}catch{$status='RESOURCE_UNVERIFIED';$detail='OUTPUT_UNVERIFIED'}}}
 if($out){$out.Flush($true);$out.Dispose()};if($err){$err.Flush($true);$err.Dispose()}
 if($final -and ($final.CpuSeconds -gt 15 -or $final.PeakBytes -gt 512MB -or $watch.Elapsed.TotalSeconds -gt 90 -or $budget.Exceeded)){$status='RESOURCE_UNVERIFIED';$detail='FINAL_RESOURCE_LIMIT'}
 # FINAL_ARTIFACT_BUDGET: reserve64KiB for controller receipt and inventory before any success publication.
 $total=[long]((Get-ChildItem @($run,$dataBatch) -File -Recurse -ErrorAction SilentlyContinue|Measure-Object Length -Sum).Sum)
 if($total+64KB -gt 128MB){$status='RESOURCE_UNVERIFIED';$detail='FINAL_ARTIFACT_BUDGET'}
 if($final -and $final.ExitCode -ne 0 -and $diagnosticStatus -ceq 'NOT_APPLICABLE'){$diagnosticStatus='DIAGNOSTIC_INCOMPLETE'}
 if($identity -and (Test-Path (Join-Path $run 'requests.jsonl'))){$rateBudget=Test-PublicRateLedger $run $identity.Pid $nonce;if($rateBudget.status -cne 'RATE_BUDGET_PASS'){$status='RATE_BUDGET_FAIL';$detail='RATE_BUDGET_FAIL'}}
 $controllerExit=if($status -ceq 'F1_BATCH_VERIFIED'){0}else{2}
 $receipt=@{rate_budget=$rateBudget;worker_failure=$workerFailure;diagnostic_status=$diagnosticStatus;failure_receipt_sha256=if(Test-Path (Join-Path $run 'failure.json')){(Get-FileHash (Join-Path $run 'failure.json')).Hash.ToLowerInvariant()}else{$null};nonce=$nonce;marker_validation=$markersValidated;coverage='SAMPLED_DIRECT_DESCENDANTS_NOT_KERNEL_COMPLETE';controller_exit_code=$controllerExit;descendants=$descendants;descendant_admission='NONE';primary_failure=$primaryDetail;status=$status;detail=$detail;identity=$identity;final=$final;wall_seconds=$watch.Elapsed.TotalSeconds;unexpected_descendant=$observedChild;resource_monitor_full_acceptance='BLOCKED';historical_stage_a_resource_acceptance='BLOCKED';native_isolation='NOT_QUALIFIED';physical_g1='NOT_AUTHORIZED';trading='NO-GO'}
 $receipt.functional_result_sha256=if(Test-Path (Join-Path $run 'result.json')){(Get-FileHash (Join-Path $run 'result.json')).Hash.ToLowerInvariant()}else{$null}
 Write-DiagnosticEvidence (Join-Path $run 'controller.json') $receipt;$child.Dispose()
 Get-ChildItem $run -File -Recurse|ForEach-Object {@{file=[IO.Path]::GetRelativePath($run,$_.FullName);sha256=(Get-FileHash $_.FullName).Hash.ToLowerInvariant()}}|ConvertTo-Json|Set-Content (Join-Path $run 'EVIDENCE_SHA256.json')
}
exit $controllerExit
