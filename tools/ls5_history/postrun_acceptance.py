"""Independent current-tip acceptance, separate from precommit ledger consistency.
No network, collection, strategy or recovery. Reading evidence never grants execution.
"""
import json,hashlib,re,math
from pathlib import Path
from history_verify import verify_checkpoint,strict_json,sha

def committed_tip(path,pin):
 path=Path(path).resolve()
 if path.name!='checkpoint.json' or not re.fullmatch('batch-[0-9]{4}',path.parent.name):raise ValueError('CHECKPOINT_PATH_IDENTITY')
 state_path=path.parent.parent/'session-state.json'
 if state_path.is_symlink() or state_path.stat().st_size>65536:raise ValueError('STATE_IDENTITY_OR_BOUND')
 before=state_path.read_bytes();state=strict_json(before)
 expected={'state':'COMMITTED','checkpoint':path.parent.name+'/checkpoint.json','checkpoint_sha256':pin}
 if state!=expected:raise ValueError('NOT_CURRENT_COMMITTED_TIP')
 result=verify_checkpoint(path,pin)
 if state_path.read_bytes()!=before:raise ValueError('STATE_CHANGED_DURING_ACCEPTANCE')
 return dict(status='CURRENT_COMMITTED_CHECKPOINT_VERIFIED',history_state=result['history_state'],coverage=result['coverage'],checkpoint_sha256=pin,source_sha256=result['source_sha256'],real_oos='NOT_AUTHORIZED',physical_execution='NOT_GRANTED_BY_VERIFICATION')

def physical_postrun(path,pin,controller_path,controller_pin,expected_root):
 path=Path(path).resolve();root=Path(expected_root).resolve();controller_path=Path(controller_path).resolve()
 if path.parent.parent!=root or not re.fullmatch('[a-f0-9]{64}',controller_pin) or controller_path!=root/('attempt-'+path.parent.name[-4:])/'controller.json':raise ValueError('PHYSICAL_ROOT_OR_CONTROLLER_IDENTITY')
 if controller_path.stat().st_size>256*1024:raise ValueError('CONTROLLER_BOUND')
 if sha(controller_path)!=controller_pin:raise ValueError('CONTROLLER_SHA')
 c=strict_json(controller_path.read_bytes())
 if c.get('status')!='F1_BATCH_VERIFIED' or c.get('controller_exit_code')!=0 or c.get('unexpected_descendant') is not False or c.get('marker_validation') is not True or c.get('rate_budget',{}).get('status')!='RATE_BUDGET_PASS':raise ValueError('CONTROLLER_ADMISSION')
 final=c['final']
 if any(type(x) not in (int,float) or not math.isfinite(x) for x in (final.get('CpuSeconds'),c.get('wall_seconds'))) or type(final.get('PeakBytes')) is not int:raise ValueError('RESOURCE_TYPES')
 if final.get('Liveness')!='EXITED' or final.get('HasExited') is not True:raise ValueError('FINAL_LIVENESS')
 if final.get('ExitCode')!=0 or final.get('Pid')!=c['identity']['Pid'] or final.get('Created')!=c['identity']['Created'] or not 0<=final['CpuSeconds']<=15 or not 0<=c['wall_seconds']<=90 or not 0<=final['PeakBytes']<=512*1048576:raise ValueError('RESOURCE_OR_PROCESS_IDENTITY')
 result_path=controller_path.parent/'result.json'
 if result_path.stat().st_size>256*1024:raise ValueError('RESULT_BOUND')
 if sha(result_path)!=c.get('functional_result_sha256'):raise ValueError('RESULT_SHA')
 r=strict_json(result_path.read_bytes())
 if r.get('status')!='F1_BATCH_VERIFIED' or r.get('batch_index')!=int(path.parent.name[-4:]):raise ValueError('RESULT_BATCH_IDENTITY')
 if r.get('checkpoint_sha256')!=pin or r.get('nonce')!=c.get('nonce') or r.get('pid')!=c['identity']['Pid'] or r.get('head')!='11b6c793e6617c3de08e6ca4fa741625c54c1951' or r.get('history_state') not in ('PARTIAL','READY'):raise ValueError('RESULT_BINDING')
 total=0;batch_bytes=0
 for file in root.rglob('*'):
  if file.is_symlink() or getattr(file.lstat(),'st_file_attributes',0)&0x400:raise ValueError('LINKED_EVIDENCE')
  if file.is_file():
   size=file.stat().st_size;total+=size
   if file.is_relative_to(path.parent) or file.is_relative_to(controller_path.parent):batch_bytes+=size
 if total>2*1024**3 or batch_bytes>128*1024**2:raise ValueError('FINAL_DISK_LIMIT')
 accepted=committed_tip(path,pin)
 if accepted['history_state']!=r['history_state']:raise ValueError('HISTORY_STATE_BINDING')
 accepted['resource_acceptance']='RECORDED_DIAGNOSTIC_LIMITS_ONLY';accepted['native_isolation']='NOT_QUALIFIED';return accepted
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--checkpoint',required=True);p.add_argument('--checkpoint-sha256',required=True);p.add_argument('--controller',required=True);p.add_argument('--controller-sha256',required=True);a=p.parse_args()
 print(json.dumps(physical_postrun(a.checkpoint,a.checkpoint_sha256,a.controller,a.controller_sha256,a.root),sort_keys=True))
