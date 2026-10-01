from dataclasses import dataclass
import shutil,subprocess
@dataclass(frozen=True)
class TailscaleStatus:
    installed:bool
    running:bool
    detail:str=''
def detect_tailscale():
    exe=shutil.which('tailscale')
    if not exe:return TailscaleStatus(False,False,'not installed')
    try:
        p=subprocess.run([exe,'status','--json'],capture_output=True,text=True,timeout=10)
        return TailscaleStatus(True,p.returncode==0,'available' if p.returncode==0 else 'installed but unavailable')
    except (OSError,subprocess.SubprocessError):
        return TailscaleStatus(True,False,'status failed')
