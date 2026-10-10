from types import SimpleNamespace
import threading

import pytest

from strattester import service_guardian
from strattester.runtime.service_manager import WindowsServiceManager


def test_intentional_stop_survives_guardian_restart(tmp_path, monkeypatch):
    calls=[]
    def runner(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='STATE : 1 STOPPED' if args[-1]=='StrattesterWorker' else 'STATE : 4 RUNNING',stderr='')
    manager=WindowsServiceManager(runner,root=tmp_path)
    manager.stop()
    # A newly constructed guardian/controller must read the durable intent.
    WindowsServiceManager(runner,root=tmp_path)
    monkeypatch.setattr(service_guardian.subprocess,'run',runner)
    report=service_guardian.run(tmp_path,repair=True)
    assert ['sc.exe','start','StrattesterWorker'] not in calls
    assert report['healthy']


def test_start_clears_the_durable_stop_hold(tmp_path, monkeypatch):
    running=False
    calls=[]
    def runner(args,**kwargs):
        nonlocal running
        calls.append(args)
        if args[1]=='start' and args[-1]=='StrattesterWorker': running=True
        state='RUNNING' if running or args[-1]!='StrattesterWorker' else 'STOPPED'
        return SimpleNamespace(returncode=0,stdout=f'STATE : {4 if state=="RUNNING" else 1} {state}',stderr='')
    first=WindowsServiceManager(runner,root=tmp_path)
    first.stop()
    WindowsServiceManager(runner,root=tmp_path).start()
    monkeypatch.setattr(service_guardian.subprocess,'run',runner)
    report=service_guardian.run(tmp_path,repair=True)
    assert sum(c==['sc.exe','start','StrattesterWorker'] for c in calls)==1
    assert any(c['name']=='worker-heartbeat' and not c['ok'] for c in report['checks'])


def test_restart_waits_for_scm_to_report_stopped(tmp_path):
    calls=[]
    queries=0
    def runner(args,**kwargs):
        nonlocal queries
        calls.append(args)
        state=''
        if args[1]=='query':
            queries+=1
            state='STATE : 3 STOP_PENDING' if queries==1 else 'STATE : 1 STOPPED'
        return SimpleNamespace(returncode=0,stdout=state,stderr='')
    manager=WindowsServiceManager(runner,root=tmp_path,sleep=lambda _:None)
    manager.restart()
    assert queries==2
    assert calls[-1]==['sc.exe','start','StrattesterWorker']


def test_failed_stop_is_not_reported_as_success(tmp_path):
    def denied(*args,**kwargs):
        return SimpleNamespace(returncode=5,stdout='',stderr='access denied')
    with pytest.raises(RuntimeError,match='stop'):
        WindowsServiceManager(denied,root=tmp_path).stop()


def test_stop_disables_automatic_boot_until_explicit_start(tmp_path):
    calls=[]
    def runner(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    manager=WindowsServiceManager(runner,root=tmp_path)
    manager.stop()
    assert ['sc.exe','config','StrattesterWorker','start=','demand'] in calls
    manager.start()
    assert ['sc.exe','config','StrattesterWorker','start=','auto'] in calls


def test_guardian_cannot_restart_after_a_concurrent_stop_completes(tmp_path, monkeypatch):
    calls=[];threads=[];errors=[]
    stop_completed=threading.Event()
    running=False
    interleaved=False
    manager=None
    def stop():
        try:
            manager.stop()
            calls.append('stop-complete')
        except Exception as exc:
            errors.append(exc)
        finally:
            stop_completed.set()
    def runner(args,**kwargs):
        nonlocal running,interleaved
        if args[1]=='query' and args[-1]=='StrattesterWorker' and not interleaved:
            interleaved=True
            thread=threading.Thread(target=stop);threads.append(thread);thread.start()
            stop_completed.wait(1)
            return SimpleNamespace(returncode=0,stdout='STATE : 1 STOPPED',stderr='')
        if args[1]=='start' and args[-1]=='StrattesterWorker':
            running=True;calls.append('start')
        elif args[1]=='stop':
            running=False;calls.append('stop')
        return SimpleNamespace(returncode=0,stdout='STATE : 4 RUNNING',stderr='')
    manager=WindowsServiceManager(runner,root=tmp_path)
    monkeypatch.setattr(service_guardian.subprocess,'run',runner)
    service_guardian.run(tmp_path,repair=True)
    assert stop_completed.wait(3)
    for thread in threads: thread.join(3)
    assert not errors
    assert not running
    assert 'start' not in calls[calls.index('stop-complete')+1:]
