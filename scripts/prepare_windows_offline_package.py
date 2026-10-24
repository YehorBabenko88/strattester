"""Build a review package only. Deliberately provides no execution mode."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    sha=subprocess.run(['git','rev-parse','HEAD'],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
    dirty=bool(subprocess.run(['git','status','--porcelain','--untracked-files=no'],cwd=root,check=True,capture_output=True,text=True).stdout.strip())
    files=['docs/readiness/WINDOWS_OFFLINE_RUNNER_PLAN.md','scripts/prepare_windows_offline_package.py']
    contents={name:(root/name).read_bytes() for name in files}
    manifest={'schema':1,'source_base_sha':sha,'source_worktree_dirty':dirty,'physical_g1':'NOT_AUTHORIZED',
              'native_windows_controls':'NOT_RUN','execution_supported':False,
              'files':{name:sha256(data).hexdigest() for name,data in contents.items()}}
    # Exclusive creation: never overwrite a reviewed package or accepted result.
    with args.output.open('xb') as stream:
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in contents.items(): archive.writestr(name,data)
            archive.writestr('manifest.json',json.dumps(manifest,sort_keys=True,indent=2))
    print(json.dumps({'package_sha256':sha256(args.output.read_bytes()).hexdigest(),
                      'physical_g1':'NOT_AUTHORIZED','native_windows_controls':'NOT_RUN'}))


if __name__=='__main__': main()
