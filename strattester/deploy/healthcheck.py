from dataclasses import dataclass
import subprocess
@dataclass(frozen=True)
class HealthResult:
    ok:bool
    detail:str
def run_healthcheck(python_exe,module='strattester.doctor_cli',timeout=60):
    p=subprocess.run([str(python_exe),'-m',module],capture_output=True,text=True,timeout=timeout)
    return HealthResult(p.returncode==0,(p.stdout+p.stderr).strip())
