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

def test_control_status_reports_resources_db_and_recent_errors(tmp_path):
    import json,sqlite3
    (tmp_path/'state').mkdir(); (tmp_path/'logs').mkdir(); (tmp_path/'data').mkdir()
    db=tmp_path/'data'/'bybit_1m.sqlite3'
    con=sqlite3.connect(db); con.execute('create table candles(x integer)'); con.commit(); con.close()
    (tmp_path/'logs'/'worker.jsonl').write_text(json.dumps({'level':'ERROR','event':'boom'})+'\n')
    c=ControlStatus(tmp_path,clock=lambda:100)
    assert c.database()['exists'] is True
    assert c.resources()['disk_free']>=0
    assert c.errors(10)[0]['event']=='boom'
