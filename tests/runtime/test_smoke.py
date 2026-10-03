from strattester.smoke import run_worker_smoke

def test_worker_smoke_completes_and_persists_job(tmp_path):
    r=run_worker_smoke(tmp_path)
    assert r.ok and r.state=='COMPLETE' and r.reopened_state=='COMPLETE'

def test_worker_smoke_failure_is_retryable(tmp_path):
    r=run_worker_smoke(tmp_path,fail=True)
    assert not r.ok and r.state=='RETRYABLE' and r.reopened_state=='RETRYABLE'
