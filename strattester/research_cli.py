"""Explicit research command surface. No ordinary CLI activation or services."""
import argparse
import json
import time
from pathlib import Path

def parser():
    p=argparse.ArgumentParser(prog='python -m strattester.research_cli')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('prepare','verify','diagnose','test-disposable','report','run'):
        q=sub.add_parser(name)
        for flag in ('config','config-sha256','trust-store-sha256','openssl-exe','openssl-sha256','scratch-root'):
            q.add_argument('--'+flag)
        q.add_argument('--output');q.add_argument('--enable-research',action='store_true')
        if name=='run':
            q.add_argument('--mode',choices=('offline','connected'),default='offline')
            q.add_argument('--profile');q.add_argument('--profile-sha256');q.add_argument('--export-metadata');q.add_argument('--export-metadata-sha256');q.add_argument('--connected-output')
            q.add_argument('--sign-public-fixture',action='store_true')
        if name=='prepare':q.add_argument('--seed',type=int,default=31)
        if name=='test-disposable':
            q.add_argument('--launch',action='store_true')
            for flag in ('plan','plan-sha256','signature','signature-sha256','owner-trust-store','owner-trust-store-sha256','owner-id','target-sha','tree-sha','binary-sha256','package-sha256','node-identity'):
                q.add_argument('--'+flag)
    experiment=sub.add_parser('experiment')
    experiment.add_argument('--source',required=True);experiment.add_argument('--source-sha256',required=True)
    experiment.add_argument('--output',required=True);experiment.add_argument('--enable-research',action='store_true')
    return p

def _required(a,names):
    if any(getattr(a,n,None) is None for n in names):raise ValueError('required independent pins unavailable')

def _verifier(a):
    _required(a,('openssl_exe','openssl_sha256','scratch_root'))
    from .research.financial_signatures import OpenSSLVerifier
    if not Path(a.openssl_exe).is_absolute():raise ValueError('absolute verifier required')
    return OpenSSLVerifier(Path(a.openssl_exe),a.openssl_sha256,Path(a.scratch_root))

def _profile(path,expected_sha256):
    from dataclasses import replace
    from .research.financial_grid_exporter import HistoryProfile,HistorySource
    from .research.financial_signed_export import MarketPartition
    from .research.financial_snapshot import bounded_json,verified_bytes,reject_linked_path
    from .research.financial_session import bundle_path
    profile_path=Path(path)
    raw=bounded_json(verified_bytes(profile_path,expected_sha256,64*1024))
    sources=[]
    for row in raw['sources']:
        source=HistorySource(**{**row,'partitions':tuple(MarketPartition(**v) for v in row['partitions'])})
        if source.engine in ('sqlite','sharded_sqlite'):
            location=Path(source.location)
            location=reject_linked_path(location) if location.is_absolute() else bundle_path(profile_path.parent,source.location)
            source=replace(source,location=str(location))
        sources.append(source)
    return HistoryProfile(**{**raw,'sources':tuple(sources)})

def main(argv=None):
    a=parser().parse_args(argv)
    try:
        if a.command=='experiment':
            from .research.financial_experiment_session import run_experiment_file
            result=run_experiment_file(a.source,a.source_sha256,a.output,enable_research=a.enable_research)
        elif a.command=='prepare':
            _required(a,('output',));v=_verifier(a)
            from .research.financial_test_package import prepare_test_package
            result=prepare_test_package(a.output,openssl_exe=v.executable,openssl_sha256=v.executable_sha256,scratch_root=v.scratch_root,seed=a.seed)
        elif a.command=='test-disposable':
            _required(a,('plan','plan_sha256','signature','signature_sha256','owner_trust_store','owner_trust_store_sha256','owner_id','target_sha','tree_sha','binary_sha256','package_sha256','node_identity'))
            from .research.financial_owner_authorization import verify_owner_authorization
            verify_owner_authorization(a.plan,plan_sha256=a.plan_sha256,signature_path=a.signature,signature_sha256=a.signature_sha256,trust_store_path=a.owner_trust_store,trust_store_sha256=a.owner_trust_store_sha256,owner_id=a.owner_id,verifier=_verifier(a),now_ns=time.time_ns(),expected_target_sha=a.target_sha,expected_tree_sha=a.tree_sha,expected_binary_sha256=a.binary_sha256,expected_package_sha256=a.package_sha256,expected_node_identity=a.node_identity)
            result={'status':'BLOCKED','reason':'NATIVE_ALL_CONTROLS_NOT_INDEPENDENTLY_VERIFIED','launched':False,'physical_g1':'NOT_AUTHORIZED'}
        else:
            _required(a,('config','config_sha256','trust_store_sha256'))
            from .research.financial_session import load_session,verify_session,run_session
            s=load_session(a.config,a.config_sha256,trust_store_sha256=a.trust_store_sha256,verifier=_verifier(a))
            if a.command in ('verify','diagnose'):
                result={'status':'VERIFIED','provenance':verify_session(s)}
                if a.command=='diagnose':result.update(native_resource_caps='NOT_ENFORCED',physical_g1='NOT_AUTHORIZED',trading='NO-GO')
            else:
                kwargs={}
                if a.command=='run' and a.mode=='connected':
                    _required(a,('profile','profile_sha256','export_metadata','export_metadata_sha256','connected_output'))
                    from .research.financial_snapshot import bounded_json,verified_bytes
                    profile=_profile(a.profile,a.profile_sha256)
                    kwargs=dict(connected_profile=profile,connected_output=a.connected_output,export_metadata=bounded_json(verified_bytes(a.export_metadata,a.export_metadata_sha256,16*1024)),sign_public_fixture=a.sign_public_fixture)
                elif a.command=='run' and any((a.profile,a.profile_sha256,a.export_metadata,a.export_metadata_sha256,a.connected_output,a.sign_public_fixture)):
                    raise ValueError('offline denies connected arguments')
                result=run_session(s,enable_research=a.enable_research,mode=getattr(a,'mode','offline'),output_root=a.output if a.command=='run' else None,**kwargs)
                if a.command=='report':
                    _required(a,('output',))
                    from .research.financial_report_export import export_report
                    result=export_report(result,a.output)
        print(json.dumps(result,sort_keys=True,default=str,allow_nan=False))
        return 2 if result.get('status')=='BLOCKED' else 0
    except KeyboardInterrupt:
        print(json.dumps({'status':'CANCELLED','code':'RESEARCH_CANCELLED'}));return 130
    except Exception as exc:
        # Exception strings can contain DSNs, paths, credentials or driver text.
        print(json.dumps({'status':'BLOCKED','code':'RESEARCH_ERROR','error_type':type(exc).__name__,'physical_g1':'NOT_AUTHORIZED'}));return 2

if __name__=='__main__':raise SystemExit(main())
