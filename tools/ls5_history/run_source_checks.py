"""Machine-accounted source-only unittest runner; never a physical acceptance gate."""
import argparse,unittest,json,platform,os,sys,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
def flatten(suite):
 for case in suite:
  if isinstance(case,unittest.TestSuite):yield from flatten(case)
  else:yield case
class Result(unittest.TextTestResult):
 def startTest(self,test):super().startTest(test);self.statuses=getattr(self,'statuses',[]);self.statuses.append({'id':test.id(),'status':'STARTED'})
 def addSuccess(self,test):super().addSuccess(test);self.statuses[-1]['status']='PASSED'
 def addFailure(self,test,err):super().addFailure(test,err);self.statuses[-1]['status']='FAILED'
 def addError(self,test,err):super().addError(test,err);self.statuses[-1]['status']='ERROR'
 def addSkip(self,test,reason):super().addSkip(test,reason);self.statuses[-1]['status']='SKIPPED'
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 suite=unittest.defaultTestLoader.discover(str(HERE/'tests'));ids=[t.id() for t in flatten(suite)];required=json.loads((HERE/'REQUIRED_TEST_IDS.json').read_text());missing=sorted(set(required)-set(ids))
 with (args.output/'unittest.log').open('w') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(suite)
 report=dict(scope='SOURCE_SOFTWARE_VALIDATION_ONLY',source_sha=os.environ.get('F1_SOURCE_SHA','LOCAL_UNCOMMITTED'),os=platform.platform(),python=sys.version,collected=len(ids),executed=result.testsRun,passed=sum(t['status']=='PASSED' for t in result.statuses),failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),deselected=0,required_ids=required,missing_required=missing,tests=result.statuses,source_files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in HERE.iterdir() if f.is_file()})
 report['status']='PASS' if result.wasSuccessful() and not result.skipped and not missing and len(ids)==len(required)==result.testsRun else 'FAIL'
 (args.output/'accounting.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','source_sha','collected','executed','passed','failures','errors','skipped','deselected']}));return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
