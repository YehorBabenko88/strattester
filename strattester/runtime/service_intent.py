"""Durable operator intent shared by the controller and service guardian."""
import json
import os
from pathlib import Path
import tempfile
import sqlite3
from contextlib import contextmanager


@contextmanager
def service_control_lock(root):
    state=Path(root)/'state'
    state.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(state/'worker-control.sqlite3',timeout=180)
    try:
        # SQLite owns the OS lock, so controller/guardian crashes release it.
        connection.execute('BEGIN IMMEDIATE')
        yield
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def worker_is_stopped(root):
    path=Path(root)/'state'/'worker-intent.json'
    if not path.exists():
        return False
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or value.get('desired') not in ('running','stopped'):
        raise ValueError('invalid worker intent')
    return value['desired']=='stopped'


def set_worker_intent(root,desired):
    if desired not in ('running','stopped'):
        raise ValueError('invalid worker intent')
    state=Path(root)/'state'
    state.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='worker-intent-',suffix='.tmp',dir=state)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump({'schema':1,'desired':desired},stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,state/'worker-intent.json')
    finally:
        if os.path.exists(name):
            os.unlink(name)
