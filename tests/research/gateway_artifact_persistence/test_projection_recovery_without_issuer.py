"""Independent own-process staging recovery, with positive projection denied.

No target is recomputed and no native commitment/receipt/permission is fabricated.
These are process-exit SQLite tests, not power-loss or distributed acceptance.
"""
from pathlib import Path
import hashlib,os,subprocess,sys
import pytest
from strattester.persistence.result_store import ResultStore
from strattester.research.result_persistence import stage_gateway_research_artifact

ROOT=Path(__file__).resolve().parents[3]
PACKET=ROOT/'docs/gateway/research/evidence/btc-v1'
INTENT=hashlib.sha256(b'LOCAL_UNISSUED_RECOVERY_INTENT').hexdigest()

def crash(path,marker,phase):
    command=[sys.executable,'-I','-S','-B',str(Path(__file__).with_name('crash_projection_stage_child.py')),phase,str(path),str(marker)]
    result=subprocess.run(command,capture_output=True,timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert result.returncode==(73 if phase=='BEFORE_COMMIT' else 74),result.stderr.decode(errors='replace')
    assert marker.read_bytes()==(b'INSERT_DONE_BEFORE_COMMIT\n' if phase=='BEFORE_COMMIT' else b'STAGE_RETURNED_AFTER_COMMIT\n')

def stage(store,intent=INTENT):
    return stage_gateway_research_artifact(store,'local-stage','local-result','BTCUSDT',
        'meta.ohlcv.untouched_levels.v1','1',(PACKET/'descriptor.json').read_bytes(),
        (PACKET/'meta-result.json').read_bytes(),original_intent_sha256=intent)

def rows(store):
    return store.con.execute('SELECT stage_id,run_id,symbol,strategy_id,strategy_version,artifact_descriptor,artifact_descriptor_sha256,artifact_sha256,original_intent_sha256,publication_receipt,result_kind FROM staged_research_results ORDER BY stage_id').fetchall()

@pytest.mark.parametrize('phase',['BEFORE_COMMIT','AFTER_COMMIT'])
def test_actual_process_exit_stage_reopen_and_exact_retry_without_publication(tmp_path,phase):
    path=tmp_path/'own.sqlite';marker=tmp_path/'phase.marker'
    ResultStore.open(path).close();crash(path,marker,phase)
    store=ResultStore.open(path)
    try:
        assert store.integrity_check()
        assert len(rows(store))==(0 if phase=='BEFORE_COMMIT' else 1)
        # Absence of a LOCAL stage says nothing about a native original outcome.
        # Projection has no issuer: neither boundary may create a public result.
        before=rows(store)
        with pytest.raises(RuntimeError,match='ARTIFACT_AUTHORITY_ABI_UNAVAILABLE'):
            store.project_gateway_artifact_commit('local-stage',actual_receipt_handle=None,expected_authority=None)
        assert rows(store)==before
        assert store.con.execute('SELECT COUNT(*) FROM research_results').fetchone()[0]==0
        assert stage(store) is None
        expected=rows(store);assert len(expected)==1 and expected[0][-2:] == (None,'ARTIFACT')
        assert expected[0][5]==(PACKET/'descriptor.json').read_bytes()
        assert expected[0][8]==INTENT
    finally:store.close()
    reopened=ResultStore.open(path)
    try:
        assert rows(reopened)==expected and stage(reopened) is None and rows(reopened)==expected
        with pytest.raises(RuntimeError,match='ARTIFACT_AUTHORITY_ABI_UNAVAILABLE'):
            reopened.read_gateway_artifact('local-result','BTCUSDT','meta.ohlcv.untouched_levels.v1','1')
        assert rows(reopened)==expected
    finally:reopened.close()

def test_postcommit_crash_conflicting_intent_never_rekeys_or_erases_unknown_stage(tmp_path):
    path=tmp_path/'own.sqlite';marker=tmp_path/'phase.marker'
    ResultStore.open(path).close();crash(path,marker,'AFTER_COMMIT')
    store=ResultStore.open(path)
    try:
        original=rows(store)
        with pytest.raises(ValueError,match='ARTIFACT_STAGE_CONFLICT'):
            stage(store,hashlib.sha256(b'DIFFERENT_UNISSUED_INTENT').hexdigest())
        assert rows(store)==original and original[0][-2] is None
        assert store.recover_staged(lambda *args:(_ for _ in ()).throw(AssertionError('legacy validator must not see artifact')))=={'promoted':0,'discarded':0}
        assert rows(store)==original and store.cleanup_staged(10**12)==0
        assert store.con.execute('SELECT COUNT(*) FROM research_results').fetchone()[0]==0
    finally:store.close()
