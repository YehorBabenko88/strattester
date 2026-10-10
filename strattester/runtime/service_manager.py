from __future__ import annotations
import subprocess
import time
from pathlib import Path
from .service_intent import set_worker_intent,service_control_lock
class WindowsServiceManager:
    def __init__(self,runner=subprocess.run,root=None,clock=time.monotonic,sleep=time.sleep,stop_timeout=30):
        self.runner=runner;self.root=Path.cwd() if root is None else Path(root)
        self.clock=clock;self.sleep=sleep;self.stop_timeout=stop_timeout
    def _sc(self,*args):
        return self.runner(['sc.exe',*args],capture_output=True,text=True,timeout=30)
    def _checked(self,*args,allowed=()):
        result=self._sc(*args)
        if result.returncode not in (0,*allowed):
            raise RuntimeError(f'sc {args[0]} failed: {result.returncode}')
        return result
    def _start(self):
        self._checked('config','StrattesterWorker','start=','auto')
        set_worker_intent(self.root,'running')
        self._checked('start','StrattesterWorker',allowed=(1056,))
    def start(self):
        with service_control_lock(self.root):
            self._start()
    def _stop(self):
        # Persist before the SCM request: guardian/reboot must not undo STOP.
        set_worker_intent(self.root,'stopped')
        self._checked('stop','StrattesterWorker',allowed=(1062,))
        self._checked('config','StrattesterWorker','start=','demand')
    def stop(self):
        with service_control_lock(self.root):
            self._stop()
    def restart(self):
        with service_control_lock(self.root):
            self._stop()
            deadline=self.clock()+self.stop_timeout
            while True:
                state=self._checked('query','StrattesterWorker')
                if 'STOPPED' in state.stdout:
                    break
                if self.clock()>=deadline:
                    raise TimeoutError('worker stop timed out')
                self.sleep(.1)
            self._start()
    def drain(self): self._checked('control','StrattesterWorker','128')
    def remove_worker(self):
        with service_control_lock(self.root):
            self._stop()
            self._checked('delete','StrattesterWorker',allowed=(1060,))
    def status(self):
        p=self._sc('query','StrattesterWorker')
        return (p.stdout+p.stderr).strip()
