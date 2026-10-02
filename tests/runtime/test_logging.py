import json
from strattester.runtime.logging import build_logger
def test_structured_log_contains_context(tmp_path):
    p=tmp_path/'a.log'; l=build_logger(p,'test-json')
    l.info('started',extra={'job_id':'j1','symbol':'BTCUSDT'})
    for h in l.handlers:h.flush()
    d=json.loads(p.read_text())
    assert d['job_id']=='j1' and d['symbol']=='BTCUSDT' and d['event']=='started'
