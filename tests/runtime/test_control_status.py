from pathlib import Path
from strattester.runtime.control_status import ControlStatus

def test_control_status_reports_worker_heartbeat_and_tail_logs(tmp_path):
    state=tmp_path/'state'; logs=tmp_path/'logs'; state.mkdir(); logs.mkdir()
    (state/'worker-heartbeat').write_text('100')
    (logs/'worker.jsonl').write_text('a\nb\nc\n')
    c=ControlStatus(tmp_path,clock=lambda:105)
    s=c.status()
    assert s['worker']=='UP' and s['heartbeat_age_seconds']==5
    assert c.tail_log('worker',2)==['b','c']

def test_stale_heartbeat_is_down(tmp_path):
    (tmp_path/'state').mkdir(); (tmp_path/'state'/'worker-heartbeat').write_text('1')
    (tmp_path/'logs').mkdir()
    assert ControlStatus(tmp_path,clock=lambda:100,stale_after=30).status()['worker']=='DOWN'
