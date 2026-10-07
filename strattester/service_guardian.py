from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, os, shutil, subprocess, time

@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    repaired: bool = False

def _service(name: str, repair: bool) -> Check:
    q=subprocess.run(["sc.exe","query",name],capture_output=True,text=True)
    if q.returncode != 0: return Check(f"service:{name}",False,"service missing")
    running="RUNNING" in q.stdout
    if running: return Check(f"service:{name}",True,"running")
    if repair:
        s=subprocess.run(["sc.exe","start",name],capture_output=True,text=True)
        if s.returncode==0 or "RUNNING" in s.stdout:
            return Check(f"service:{name}",True,"restarted",True)
    return Check(f"service:{name}",False,"not running")

def run(root: Path, repair: bool=True) -> dict:
    checks=[]
    for name in ("Tailscale","sshd","StrattesterWorker"):
        checks.append(_service(name,repair))
    usage=shutil.disk_usage(root)
    free_gb=usage.free/(1024**3)
    checks.append(Check("disk",free_gb>=5,f"{free_gb:.1f} GiB free"))
    hb=root/"state"/"worker-heartbeat"
    age=None if not hb.exists() else max(0,time.time()-hb.stat().st_mtime)
    checks.append(Check("worker-heartbeat",age is not None and age<120,"missing" if age is None else f"{age:.0f}s old"))
    status={"hostname":os.environ.get("COMPUTERNAME",""),"healthy":all(x.ok for x in checks),"checks":[asdict(x) for x in checks],"ts":time.time()}
    state=root/"state"; state.mkdir(parents=True,exist_ok=True)
    tmp=state/"guardian-status.tmp"; dst=state/"guardian-status.json"
    tmp.write_text(json.dumps(status,sort_keys=True),encoding="utf-8"); os.replace(tmp,dst)
    return status

def main():
    root=Path(os.getenv("STRATTESTER_ROOT",r"C:\ProgramData\Strattester"))
    while True:
        run(root,repair=True)
        time.sleep(60)

if __name__=="__main__": main()
