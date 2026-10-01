from __future__ import annotations
import subprocess
class WindowsServiceManager:
    def __init__(self,runner=subprocess.run): self.runner=runner
    def _sc(self,*args):
        return self.runner(['sc.exe',*args],capture_output=True,text=True,timeout=30)
    def start(self): self._sc('start','StrattesterWorker')
    def stop(self): self._sc('stop','StrattesterWorker')
    def restart(self): self.stop(); self.start()
    def drain(self): self._sc('control','StrattesterWorker','128')
    def remove_worker(self): self.stop(); self._sc('delete','StrattesterWorker')
    def status(self):
        p=self._sc('query','StrattesterWorker')
        return (p.stdout+p.stderr).strip()
