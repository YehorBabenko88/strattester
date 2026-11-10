"""Own-process SQLite boundary probe; never an authority/target/receipt issuer."""
from pathlib import Path
import hashlib,os,sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from strattester.persistence.result_store import ResultStore
from strattester.research.result_persistence import stage_gateway_research_artifact

def main():
    mode,path,marker=sys.argv[1:]
    if mode not in ('BEFORE_COMMIT','AFTER_COMMIT'):raise ValueError('own fixed probe phase required')
    path=Path(path);marker=Path(marker)
    if not path.is_absolute() or not marker.is_absolute():raise ValueError('own absolute fixture paths required')
    def no_external(event,args):
        if event=='subprocess.Popen' or event.startswith('socket.'):
            raise AssertionError('no external child/provider/native invocation')
    sys.addaudithook(no_external)
    packet=ROOT/'docs/gateway/research/evidence/btc-v1'
    descriptor=(packet/'descriptor.json').read_bytes();artifact=(packet/'meta-result.json').read_bytes()
    assert hashlib.sha256(descriptor).hexdigest()=='664d34f06721b3d62404ea2f05b6b929a59b9e3eeecc281a71d2ca927c802cda'
    assert hashlib.sha256(artifact).hexdigest()=='f4997d7d26211676cd8664e53d7999f8b71f203510f3b9a275b439c403e03940'
    store=ResultStore.open(path)
    if mode=='BEFORE_COMMIT':
        def before_commit(sql):
            if sql.strip().upper()=='COMMIT':
                marker.write_bytes(b'INSERT_DONE_BEFORE_COMMIT\n')
                os._exit(73)  # Real process exit: no Python rollback/finally runs.
        store.con.set_trace_callback(before_commit)
    stage_gateway_research_artifact(store,'local-stage','local-result','BTCUSDT',
        'meta.ohlcv.untouched_levels.v1','1',descriptor,artifact,
        original_intent_sha256=hashlib.sha256(b'LOCAL_UNISSUED_RECOVERY_INTENT').hexdigest())
    marker.write_bytes(b'STAGE_RETURNED_AFTER_COMMIT\n')
    os._exit(74)

if __name__=='__main__':main()
