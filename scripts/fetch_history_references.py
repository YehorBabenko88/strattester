"""Fetch public immutable CI references. No credentials or floating branches."""
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
pins=json.loads((root/'docs/integration/history-reference-pins.json').read_text())
for name in ('grid','math','terminan'):
    pin=pins[name];target=root/'.history-evidence'/'timed-v11'/name
    # Reruns may reuse only an already verified clean exact-pinned checkout.
    if target.exists():
        def existing(*a):return subprocess.check_output(['git','-C',str(target),*a],timeout=15).decode().strip()
        if (existing('rev-parse','HEAD')!=pin['commit'] or existing('rev-parse','HEAD^{tree}')!=pin['tree']
            or existing('status','--porcelain')):raise ValueError('REFERENCE_PIN_OR_DIRTY')
        continue
    target.mkdir(parents=True,exist_ok=False)
    def git(*a):return subprocess.check_output(['git','-C',str(target),*a],timeout=90).decode().strip()
    git('init');git('remote','add','origin','https://github.com/YehorBabenko88/'+pin['repository']+'.git')
    git('fetch','--depth=1','origin',pin['commit']);git('checkout','--detach','FETCH_HEAD')
    if git('rev-parse','HEAD')!=pin['commit'] or git('rev-parse','HEAD^{tree}')!=pin['tree']:raise ValueError('REFERENCE_PIN')
