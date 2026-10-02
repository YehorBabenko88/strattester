from strattester.runtime.bootstrap_worker import build_worker
def test_worker_bootstrap_has_durable_state(tmp_path):
    b,state,runtime=build_worker(tmp_path,lambda job:None)
    assert b.state_db.exists()
    assert runtime.state_store is state
    state.close()
