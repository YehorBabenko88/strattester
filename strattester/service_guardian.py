from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, os, shutil, subprocess, time
from .runtime.service_intent import worker_is_stopped,service_control_lock

@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    repaired: bool = False

def _service(name: str, repair: bool) -> Check:
    q=subprocess.run(["sc.exe","query",name],capture_output=True,text=True,timeout=30)
    if q.returncode != 0: return Check(f"service:{name}",False,"service missing")
    running="RUNNING" in q.stdout
    if running: return Check(f"service:{name}",True,"running")
    if repair:
        s=subprocess.run(["sc.exe","start",name],capture_output=True,text=True,timeout=30)
        if s.returncode==0 or "RUNNING" in s.stdout:
            return Check(f"service:{name}",True,"restarted",True)
    return Check(f"service:{name}",False,"not running")

def run(root: Path, repair: bool=True) -> dict:
    checks=[]
    for name in ("Tailscale","sshd"):
        checks.append(_service(name,repair))
    with service_control_lock(root):
        try:
            stopped=worker_is_stopped(root)
        except (OSError,ValueError):
            stopped=True
            checks.append(Check('worker-intent',False,'invalid intent; worker automatic start disabled'))
        worker=_service('StrattesterWorker',repair and not stopped)
        if stopped:
            worker=Check('service:StrattesterWorker',not worker.ok,
                         'stop requested; still running' if worker.ok else 'intentionally stopped')
    checks.append(worker)
    usage=shutil.disk_usage(root)
    free_gb=usage.free/(1024**3)
    checks.append(Check("disk",free_gb>=5,f"{free_gb:.1f} GiB free"))
    hb=root/"state"/"worker-heartbeat"
    age=None if not hb.exists() else max(0,time.time()-hb.stat().st_mtime)
    checks.append(Check("worker-heartbeat",stopped or (age is not None and age<120),
                        'intentionally stopped' if stopped else ('missing' if age is None else f"{age:.0f}s old")))
    status={"hostname":os.environ.get("COMPUTERNAME",""),"healthy":all(x.ok for x in checks),"checks":[asdict(x) for x in checks],"ts":time.time()}
    state=root/"state"; state.mkdir(parents=True,exist_ok=True)
    tmp=state/"guardian-status.tmp"; dst=state/"guardian-status.json"
    tmp.write_text(json.dumps(status,sort_keys=True),encoding="utf-8"); os.replace(tmp,dst)
    return status

def main():
    root=Path(os.getenv("STRATTESTER_ROOT") or Path.cwd())
    while True:
        run(root,repair=True)
        time.sleep(60)

if __name__=="__main__": main()
