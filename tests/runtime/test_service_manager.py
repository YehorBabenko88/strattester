from strattester.runtime.service_manager import WindowsServiceManager
def test_manager_targets_only_worker():
    calls=[]
    class R: stdout='';stderr='';returncode=0
    def run(args,**kw): calls.append(args);return R()
    m=WindowsServiceManager(run);m.stop();m.start()
    assert calls[0][-1]=='StrattesterWorker' and calls[1][-1]=='StrattesterWorker'
    assert all('StrattesterController' not in c for row in calls for c in row)
