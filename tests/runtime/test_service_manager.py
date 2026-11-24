from strattester.runtime.service_manager import WindowsServiceManager
def test_manager_targets_only_worker(tmp_path):
    calls=[]
    class R: stdout='';stderr='';returncode=0
    def run(args,**kw): calls.append(args);return R()
    m=WindowsServiceManager(run, root=tmp_path);m.stop();m.start()
    assert ['sc.exe','stop','StrattesterWorker'] in calls
    assert ['sc.exe','start','StrattesterWorker'] in calls
    assert all('StrattesterController' not in c for row in calls for c in row)
