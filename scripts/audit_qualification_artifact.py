"""Read-only pinned gate ZIP audit. Expected exit2 even when consistent."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strattester.research.financial_ci_artifacts import audit_gate_archive
from strattester.research.financial_executable_inventory import _local_path
from strattester.research.financial_snapshot import bounded_json,verified_bytes


def main(argv=None):
    p=argparse.ArgumentParser()
    for flag in ('archive','metadata','metadata-sha256','required-manifest','required-manifest-sha256','sha','gate'):
        p.add_argument('--'+flag,required=True)
    p.add_argument('--run',type=int,required=True);p.add_argument('--repository',type=int,required=True)
    a=p.parse_args(argv)
    try:
        manifest=bounded_json(verified_bytes(_local_path(a.required_manifest),a.required_manifest_sha256,4*1024*1024))
        result=audit_gate_archive(archive_path=a.archive,metadata_path=a.metadata,metadata_sha256=a.metadata_sha256,
            expected_sha=a.sha,expected_run=a.run,expected_repository=a.repository,gate=a.gate,
            required_nodeids=manifest[a.gate]['nodeids'])
    except Exception as exc:
        result={'status':'BLOCKED','artifact_consistency':'REJECTED','error_type':type(exc).__name__,
                'physical_g1':'NOT_AUTHORIZED','deployment':'NO-GO','trading':'NO-GO'}
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 2


if __name__=='__main__':raise SystemExit(main())
