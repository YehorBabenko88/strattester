"""Compute fresh v2 output from retained actual Root query; no query reissue."""
import argparse,hashlib,json,pathlib,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from support import canonical,load_adapter,source_root,PINS
from test_query_bridge_v2 import captured,wrapper
ROOT=pathlib.Path(__file__).resolve().parents[2]
def generate(directory):
 directory=pathlib.Path(directory);directory.mkdir(parents=True,exist_ok=False)
 a,b=captured();q=canonical(wrapper(a,b));m=load_adapter()
 out=m.execute_query_synthetic_research(q,upstream_query_request_bytes=a,upstream_query_result_bytes=b,meta_source_root=str(source_root()),cancel_check=lambda:False)
 assert out==m.execute_query_synthetic_research(q,upstream_query_request_bytes=a,upstream_query_result_bytes=b,meta_source_root=str(source_root()),cancel_check=lambda:False)
 files={'upstream-request.json':a,'upstream-result.json':b,'request.json':q,'meta-result.json':out['artifact_bytes'],'descriptor.json':canonical(out['descriptor'])}
 for name,raw in files.items():(directory/name).write_bytes(raw)
 def git(*args):return subprocess.check_output(['git','--no-replace-objects',*args],cwd=ROOT).decode().strip()
 receipt={'scope':'LOCAL_PURE_V2_COMPUTATION_FROM_RETAINED_ACTUAL_ROOT_QUERY','head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'adapter_sha256':hashlib.sha256((ROOT/'strattester/research/gateway_adapter.py').read_bytes()).hexdigest(),'query_head':m.QUERY_HEAD,'root_query_capture_source':'f155126a95e80139b1b9679c1870ffd66c29360e','query_execution':'ROOT_REPORTED_NOT_REEXECUTED_BY_THIS_RECIPE','meta_head':m.META_HEAD,'meta_tree':m.META_TREE,'meta_source_sha256':PINS,'replay':'BYTE_IDENTICAL','files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in files.items()},'source_authenticity':'NOT_EVALUATED','publication':'NONE','job_submitted':False,'native_admission':False,'physical_admission':False}
 (directory/'computation-receipt.json').write_bytes(canonical(receipt));return receipt
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
 print(json.dumps(generate(args.output),indent=2))
