"""Fetch public immutable CI references. No credentials or floating branches."""
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
pins=json.loads((root/'docs/integration/history-reference-pins.json').read_text())
for name in ('grid','math'):
    pin=pins[name];target=root/'.history-evidence'/name
    target.mkdir(parents=True,exist_ok=False)
    def git(*a):return subprocess.check_output(['git','-C',str(target),*a],timeout=90).decode().strip()
    git('init');git('remote','add','origin','https://github.com/YehorBabenko88/'+pin['repository']+'.git')
    git('fetch','--depth=1','origin',pin['commit']);git('checkout','--detach','FETCH_HEAD')
    if git('rev-parse','HEAD')!=pin['commit'] or git('rev-parse','HEAD^{tree}')!=pin['tree']:raise ValueError('REFERENCE_PIN')
