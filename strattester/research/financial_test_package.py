"""Reproducible PUBLIC synthetic test package; never an owner credential bundle."""
from dataclasses import asdict
from hashlib import sha256
import base64
import importlib.metadata
import json
from pathlib import Path
import os
import platform
import subprocess
import sys
import tempfile
import zipfile
from .financial_contract import Bar,Instrument,Snapshot,integer
from .financial_snapshot import canonical_bytes,snapshot_bytes,verified_bytes,reject_linked_path
from .financial_signed_export import SNAPSHOT_SCHEMA_SHA256,SIGNATURE_DOMAIN
from .financial_signatures import OpenSSLVerifier

RUNTIME_FILES=('scripts/audit_qualification_artifact.py','scripts/financial-gate-manifest.json',
 'strattester/__init__.py','strattester/research_cli.py','strattester/readonly_api.py','strattester/research/__init__.py',
 'strattester/strategies/__init__.py','strattester/strategies/base.py','strattester/strategies/registry.py',
 'strattester/strategies/builtin/__init__.py','strattester/strategies/builtin/financial_structural.py',
 'strattester/engine/__init__.py','strattester/engine/executor.py','strattester/marketdata/__init__.py','strattester/marketdata/datasets.py')
RESEARCH_MODULES=('financial_g0_preflight','financial_ci_artifacts','financial_acceptance',
 'financial_calibration','financial_checkpoint_replay','financial_walkforward_funding',
 'financial_g0_receipt','financial_g0_evidence','financial_contract','financial_snapshot','financial_signed_export','financial_signatures','financial_checkpoint',
 'financial_structural_model','financial_pipeline','financial_training','financial_torch_runtime','financial_executable_inventory','financial_evaluation','financial_funding','financial_authenticated_funding','financial_experiment','financial_offline_jobs',
 'financial_attested_inference','financial_owner_authorization','financial_owner_intent_v2','financial_test_package','financial_session','financial_report_export','financial_experiment_session',
 'financial_walkforward_session','financial_walkforward_fixture','financial_grid_exporter','grid_producer_readiness','alphafold_msa_attention','alphafold_outer_product','alphafold_pair_stack',
 'alphafold_triangle','alphafold_triangle_attention','alphafold_security')


def prepare_test_package(output_dir,*,openssl_exe,openssl_sha256,scratch_root,seed=31,native_binary=None,native_binary_sha256=None):
    import torch
    from .financial_structural_model import StructuralConfig,build_structural_model
    from .financial_pipeline import feature_tracks
    from .financial_training import fit_structural
    from .financial_checkpoint import save_checkpoint
    integer(seed,'seed')
    target=Path(output_dir).absolute();reject_linked_path(target.parent)
    archive=target.with_suffix('.zip')
    if target.exists() or archive.exists():raise ValueError('package destination exists; refusing overwrite')
    verifier=OpenSSLVerifier(Path(openssl_exe),openssl_sha256,Path(scratch_root))
    verified_bytes(verifier.executable,openssl_sha256,64*1024*1024)
    binary_data=None
    if native_binary is not None:
        if native_binary_sha256 is None:raise ValueError('independent native binary pin required')
        binary_data=verified_bytes(native_binary,native_binary_sha256,8*1024*1024)
    elif native_binary_sha256 is not None:raise ValueError('native binary missing')
    repo=Path(__file__).resolve().parents[2]
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    tree_sha=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip())
    stage=Path(tempfile.mkdtemp(prefix='.research-package-',dir=target.parent))
    def write(name,data):
        path=stage/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    origin=1_800_000_000_000;epoch='public-software-fixture-'+str(seed);rows=[]
    for symbol in ('BTCUSDT','ETHUSDT','SOLUSDT'):
        for tf in (60_000_000_000,300_000_000_000):
            for i in range(3):
                t=origin-(3-i)*tf
                rows.append(Bar(Instrument('bybit','linear',symbol),tf,t,t+tf,t+tf-1,t+tf,t+tf,origin,100.+i+seed*.001,'VERIFIED',True,True,1,'fixture-grid',source_sha))
    snapshot=Snapshot(tuple(rows),origin,epoch,('fixture-grid',)).validate();data=snapshot_bytes(snapshot);dataset_sha=sha256(data).hexdigest();write('snapshot.json',data)
    partitions=[dict(exchange='bybit',market_type='linear',symbol=s,timeframe_ns=tf) for s in ('BTCUSDT','ETHUSDT','SOLUSDT') for tf in (60_000_000_000,300_000_000_000)]
    manifest=dict(version=1,producer_id='fixture-grid',producer_build_sha=source_sha,key_id='rfc-key',export_id='public-software-fixture',coherence_epoch_id=epoch,snapshot_schema_version=1,snapshot_schema_sha256=SNAPSHOT_SCHEMA_SHA256,snapshot_sha256=dataset_sha,snapshot_bytes=len(data),row_count=len(rows),knowledge_cutoff_ns=origin,issued_at_ns=origin+1,scope='SYNTHETIC_ENGINEERING_ONLY',partitions=partitions,
        sources=[dict(source_id='public-fixture',engine='fixture',schema_sha256=SNAPSHOT_SCHEMA_SHA256,snapshot_id='immutable-seed-'+str(seed),coherence_epoch_id=epoch,complete=True,first_availability_retained=True,revision_history_retained=True,event_watermark_ns=origin,availability_watermark_ns=origin)])
    # Public RFC8032 test2 key, intentionally NOT a production producer/owner key.
    key_seed=bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb')
    public=bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
    with tempfile.TemporaryDirectory(prefix='public-fixture-sign-',dir=Path(scratch_root)) as signing:
        root=Path(signing);(root/'key.der').write_bytes(bytes.fromhex('302e020100300506032b657004220420')+key_seed)
        message=SIGNATURE_DOMAIN+canonical_bytes(manifest);(root/'message').write_bytes(message);(root/'openssl.cnf').write_bytes(b'')
        env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR') if k in os.environ};env['OPENSSL_CONF']=str(root/'openssl.cnf')
        subprocess.run([str(verifier.executable),'pkeyutl','-sign','-rawin','-keyform','DER','-inkey',str(root/'key.der'),'-in',str(root/'message'),'-out',str(root/'signature')],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=True)
        signature=(root/'signature').read_bytes();verifier.verify(public,message,signature)
    manifest['signature_b64']=base64.b64encode(signature).decode();manifest_bytes=canonical_bytes(manifest);write('manifest.json',manifest_bytes);write('signature.ed25519',signature)
    trust=canonical_bytes(dict(version=1,keys=[dict(producer_id='fixture-grid',key_id='rfc-key',public_key_b64=base64.b64encode(public).decode(),valid_from_ns=0,valid_until_ns=10**20,revoked=False)]));write('trust.json',trust)
    torch.manual_seed(seed);model=build_structural_model(StructuralConfig(horizon_ns=600_000_000_000,recycles=0))
    x,mask,_=feature_tracks(snapshot,timeframe_ns=60_000_000_000,config=model.config)
    losses=fit_structural(model,x,torch.tensor([.001]),mask,seed=seed,steps=2)
    checkpoint_sha=save_checkpoint(model,stage/'checkpoint.json',dataset_sha256=dataset_sha,seed=seed)
    policy=dict(producer_id='fixture-grid',coherence_epoch_id=epoch,knowledge_cutoff_ns=origin,verification_ns=origin+10,scope='SYNTHETIC_ENGINEERING_ONLY',sources=[dict(source_id='public-fixture',engine='fixture',schema_sha256=SNAPSHOT_SCHEMA_SHA256)],partitions=partitions)
    config=dict(version=1,manifest_path='manifest.json',manifest_sha256=sha256(manifest_bytes).hexdigest(),snapshot_path='snapshot.json',checkpoint_path='checkpoint.json',checkpoint_sha256=checkpoint_sha,trust_store_path='trust.json',instrument=asdict(Instrument('bybit','linear','BTCUSDT')),timeframe_ns=60_000_000_000,horizon_ns=600_000_000_000,available_ns=origin+10,policy=policy,max_work_bytes=512*1024*1024)
    config_data=canonical_bytes(config);write('session.json',config_data)
    # Independent direct-label synthetic experiment, never a producer receipt.
    from .financial_experiment import Example
    examples=[];ns=1_000_000_000
    for at in (360,720,1080,1440,1800,2160,2520,2880,3240):
        for frame in (60,120):
            history=[]
            for k,symbol in enumerate(('BTCUSDT','ETHUSDT','SOLUSDT')):
                for j in range(3):
                    t=(at-(3-j)*frame)*ns
                    history.append(Bar(Instrument('bybit','linear',symbol),frame*ns,t,t+frame*ns,t+frame*ns-1,t+frame*ns,t+frame*ns,at*ns,100.+j+k+at/10000,'VERIFIED',True,True,1,'public-software-fixture',source_sha))
            history=Snapshot(tuple(history),at*ns,'synthetic-experiment',('public-software-fixture',))
            for k,symbol in enumerate(('BTCUSDT','ETHUSDT','SOLUSDT')):
                examples.append(asdict(Example(history,Instrument('bybit','linear',symbol),frame*ns,(at+120)*ns,.001*(k-1))))
    experiment=canonical_bytes(dict(version=1,scope='SYNTHETIC_ENGINEERING_ONLY',examples=examples,config=asdict(StructuralConfig(horizon_ns=120*ns,recycles=0)),train_end=1200*ns,validation_end=2400*ns,test_end=3400*ns,holdout_symbols=['SOLUSDT'],steps=1,seed=seed,fee_bps=2.,slippage_bps=1.,embargo_ns=0))
    write('experiment-input.json',experiment)
    write('experiment.json',canonical_bytes({'status':'SYNTHETIC_SOFTWARE_VALIDATION_ONLY','seed':seed,'initialization_seed':seed,'optimizer_steps':2,'losses':losses,'dataset_sha256':dataset_sha,'manifest_sha256':sha256(manifest_bytes).hexdigest(),'trust_store_sha256':sha256(trust).hexdigest(),'checkpoint_sha256':checkpoint_sha,'source_sha':source_sha,'tree_sha':tree_sha,'source_dirty':dirty,'model_config':asdict(model.config),'real_oos':'BLOCKED','physical_g1':'NOT_AUTHORIZED'}))
    files=[*RUNTIME_FILES,*['strattester/research/'+m+'.py' for m in RESEARCH_MODULES]]
    files.extend(str(p.relative_to(repo)).replace('\\','/') for p in (repo/'research/alphafold_training').glob('*.py'))
    code_hashes={}
    for name in sorted(set(files)):
        path=repo/name
        if not path.is_file():raise ValueError('required packaged source unavailable: '+name)
        content=path.read_bytes();code_hashes[name]=sha256(content).hexdigest();write('runtime/'+name,content)
    for path in (repo/'native/windows').glob('*'):
        if path.suffix in ('.cs','.md','.json'):write('source/native/windows/'+path.name,path.read_bytes())
    if (repo/'scripts/build_windows_native.py').is_file():write('source/scripts/build_windows_native.py',(repo/'scripts/build_windows_native.py').read_bytes())
    for name in ('scripts/physical_g0_inventory.ps1','docs/finalization/physical-plan.md'):
        path=repo/name
        if path.is_file():write('source/'+name,path.read_bytes())
    if binary_data is not None:write('native/StratTester.Native.exe',binary_data)
    lock=[]
    for distribution in importlib.metadata.distributions():
        name=distribution.metadata.get('Name')
        if name:lock.append({'name':name,'version':distribution.version,'license':distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or 'UNSPECIFIED'})
    write('dependency-lock.json',canonical_bytes({'python':sys.version,'platform':platform.platform(),'packages':sorted(lock,key=lambda x:x['name'].lower()),'automatic_install':False}))
    intent_inputs={name:sha256((stage/path).read_bytes()).hexdigest() for name,path in dict(snapshot='snapshot.json',manifest='manifest.json',checkpoint='checkpoint.json',trust_store='trust.json',session_config='session.json',experiment_source='experiment-input.json').items()}
    intent_inputs['package']=None # Fill OUTSIDE the completed ZIP; avoid a hash cycle.
    template=dict(version=2,purpose='PHYSICAL_G1_AUTHORIZATION',owner_id=None,key_id=None,target_sha=source_sha,tree_sha=tree_sha,binary_sha256=native_binary_sha256,package_sha256=None,vm_identity_sha256=None,input_hashes=intent_inputs,issued_at_ns=None,expires_at_ns=None,nonce=None,operations=['synthetic_cpu_inference'],limits=dict(cpu_percent=10,memory_bytes=2147483648,wall_seconds=60,output_bytes=67108864,max_processes=1))
    write('owner-plan-template.json',canonical_bytes(template))
    write('README.txt',b'PUBLIC SYNTHETIC SOFTWARE FIXTURE ONLY. RFC8032 producer key is publicly known and must NEVER be trusted for real data or owner authorization. No owner key is included. Source files are under runtime/. No exchange client or trading credentials are bundled. Use external config/trust hashes printed by prepare. Owner must complete/sign the plan OUTSIDE this immutable ZIP after hashing it. Native components are not full isolation; test-disposable remains BLOCKED until independently verified controls and separate owner authorization. No G1 is authorized. No synthetic profitability claim. Stop on any hash/identity/network/DB/service/resource mismatch. Preserve partial stages; no automatic destructive cleanup.\n')
    source_manifest={'version':1,'source_sha':source_sha,'tree_sha':tree_sha,'dirty':dirty,'source_files_sha256':code_hashes,'native_binary_sha256':native_binary_sha256,'native_enforcement':'NOT_QUALIFIED','physical_g1':'NOT_AUTHORIZED'}
    write('source-manifest.json',canonical_bytes(source_manifest))
    checks={str(p.relative_to(stage)).replace('\\','/'):sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()};write('artifact-manifest.json',canonical_bytes({'version':1,'files_sha256':checks,'not_an_authorization':True}))
    os.rename(stage,target)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(target.rglob('*')):
            if path.is_file():
                info=zipfile.ZipInfo(str(path.relative_to(target)).replace('\\','/'),date_time=(2000,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;zipped.writestr(info,path.read_bytes())
    return {'status':'PREPARED_PUBLIC_SOFTWARE_FIXTURE','config_path':str(target/'session.json'),'config_sha256':sha256(config_data).hexdigest(),'trust_store_sha256':sha256(trust).hexdigest(),'package_path':str(archive),'package_sha256':sha256(archive.read_bytes()).hexdigest(),'source_sha':source_sha,'tree_sha':tree_sha,'source_dirty':dirty,'native_enforcement':'NOT_QUALIFIED','physical_g1':'NOT_AUTHORIZED'}
