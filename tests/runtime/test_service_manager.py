from strattester.runtime.service_manager import WindowsServiceManager
from pathlib import Path
import json
def test_manager_targets_only_worker(tmp_path):
    cwd_paths=[Path.cwd()/'state'/name for name in ('worker-control.sqlite3','worker-intent.json')]
    before=[p.read_bytes() if p.exists() else None for p in cwd_paths]
    calls=[]
    class R: stdout='';stderr='';returncode=0
    def run(args,**kw): calls.append(args);return R()
    m=WindowsServiceManager(run,root=tmp_path);m.stop();m.start()
    assert ['sc.exe','stop','StrattesterWorker'] in calls
    assert ['sc.exe','start','StrattesterWorker'] in calls
    assert all('StrattesterController' not in c for row in calls for c in row)
    assert (tmp_path/'state/worker-control.sqlite3').is_file()
    assert json.loads((tmp_path/'state/worker-intent.json').read_bytes())=={'schema':1,'desired':'running'}
    assert [p.read_bytes() if p.exists() else None for p in cwd_paths]==before
