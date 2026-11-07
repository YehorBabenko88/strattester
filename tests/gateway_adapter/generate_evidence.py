"""Explicit disposable evidence generation, never A4 publication/receipt."""
import argparse,hashlib,json,pathlib,subprocess,sys
from support import ROOT,canonical,sha,request,reference,load_adapter,source_root,source_revision

def generate(output):
 git=pathlib.Path('C:/Program Files/Git/cmd/git.exe' if sys.platform=='win32' else '/usr/bin/git')
 def revision(value):return subprocess.check_output([str(git),'--no-replace-objects','--no-optional-locks','-c','core.fsmonitor=false','-c','core.hooksPath='+('NUL' if sys.platform=='win32' else '/dev/null'),'rev-parse',value],cwd=ROOT,text=True).strip()
 head=revision('HEAD');tree=revision('HEAD^{tree}')
 if source_revision()!=head:raise ValueError('fixture generation must name actual committed producer source')
 q=request();raw_request=canonical(q)
 adapter=load_adapter();first=adapter.execute_synthetic_research(raw_request,meta_source_root=str(source_root()),cancel_check=lambda:False)
 second=adapter.execute_synthetic_research(raw_request,meta_source_root=str(source_root()),cancel_check=lambda:False)
 if first!=second or first['artifact_bytes']!=canonical(reference(q)):raise ValueError('actual Meta replay/reference mismatch')
 raw_descriptor=canonical(first['descriptor']);raw_result=first['artifact_bytes']
 output=pathlib.Path(output);output.mkdir(parents=False,exist_ok=False)
 files=[]
 for name,raw in [('request.json',raw_request),('meta-result.json',raw_result),('descriptor.json',raw_descriptor)]:
  (output/name).write_bytes(raw);files.append({'path':name,'bytes':len(raw),'sha256':sha(raw)})
 receipt={'schema':'agent7.synthetic.computation.evidence.v1','scope':'LOCAL_COMPUTATION_NOT_PUBLICATION_OR_RUNTIME_ADMISSION','adapter_head':head,'adapter_tree':tree,'fixture_producer_head':head,'adapter_file_sha256':sha((ROOT/'strattester/research/gateway_adapter.py').read_bytes()),'generator_file_sha256':sha(pathlib.Path(__file__).read_bytes()),'meta_head':adapter.META_HEAD,'meta_tree':adapter.META_TREE,'meta_source_sha256':adapter.SOURCE_PINS,'python':sys.version.split()[0],'operation':adapter.OPERATION,'actual_function':'meta_analyse.ohlcv_research_adapter.analyze_ohlcv_research','clock_policy':'EXPLICIT_SYNTHETIC_ANALYSIS_CLOCK','deterministic_replay':'BYTE_IDENTICAL','reference_comparison':'BYTE_IDENTICAL_REAL_META','publication':'NONE','job_submission':'NONE','native_admission':'BLOCKED','financial_profile':'NONE','files':files}
 (output/'computation-receipt.json').write_bytes(canonical(receipt)+b'\n')
 return receipt
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();print(json.dumps(generate(args.output)))
