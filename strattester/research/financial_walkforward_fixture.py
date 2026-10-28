"""Reproducible PUBLIC RFC8032 synthetic fixture; no real-data authority."""
from dataclasses import asdict
from hashlib import sha256
import base64
import os
from pathlib import Path
import subprocess
import tempfile
from .financial_contract import Instrument, Bar, Snapshot, integer
from .financial_snapshot import canonical_bytes, snapshot_bytes, reject_linked_path, verified_bytes
from .financial_signed_export import SIGNATURE_DOMAIN, SNAPSHOT_SCHEMA_SHA256
from .financial_signatures import OpenSSLVerifier
from .financial_session import check_cancel

PUBLIC = bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
SEED = bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb')


def prepare_walkforward_fixture(output_dir, *, openssl_exe, openssl_sha256, scratch_root, seed=31,
                                instruments=None, timeframes_ns=(60_000_000_000,120_000_000_000),
                                horizon_ns=120_000_000_000, cancel=lambda: False):
    import torch
    from .financial_structural_model import StructuralConfig, build_structural_model
    from .financial_checkpoint import save_checkpoint
    check_cancel(cancel);integer(seed,'seed');integer(horizon_ns,'horizon',1)
    instruments = tuple(instruments) if instruments is not None else tuple(Instrument('bybit','linear',s) for s in ('BTCUSDT','ETHUSDT','SOLUSDT'))
    frames=tuple(timeframes_ns)
    if not 2 <= len(instruments) <= 3 or len(set(instruments)) != len(instruments):raise ValueError('fixture instrument budget')
    for instrument in instruments:instrument.validate()
    if len({i.symbol for i in instruments}) != len(instruments):raise ValueError('fixture requires distinct holdout symbols')
    if not 1 <= len(frames) <= 2 or len(set(frames)) != len(frames):raise ValueError('fixture timeframe budget')
    for tf in frames:
        integer(tf,'timeframe',1)
        if horizon_ns % tf:raise ValueError('fixture horizon alignment')
    target=Path(output_dir);root=reject_linked_path(target.parent)
    if target.exists() or target.is_symlink():raise ValueError('fixture output exists')
    executable=Path(openssl_exe)
    if not executable.is_absolute():raise ValueError('absolute pinned signer required')
    verified_bytes(executable,openssl_sha256,64*1024*1024)
    scratch=reject_linked_path(scratch_root);verifier=OpenSSLVerifier(executable,openssl_sha256,scratch)
    config=StructuralConfig(horizon_ns=horizon_ns,recycles=0,max_batch=32)
    with tempfile.TemporaryDirectory(prefix='.walkforward-fixture-',dir=root) as temporary:
        stage=Path(temporary)
        def write(name,data):
            check_cancel(cancel)
            with (stage/name).open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            return sha256(data).hexdigest()
        trust=canonical_bytes(dict(version=1,keys=[dict(producer_id='fixture-grid',key_id='rfc-key',public_key_b64=base64.b64encode(PUBLIC).decode(),valid_from_ns=0,valid_until_ns=10**30,revoked=False)]))
        trust_sha=write('trust.json',trust)
        exports=[];labels=[];epoch='public-walkforward-fixture';build_sha='a'*40
        partitions=[dict(exchange=i.exchange,market_type=i.market_type,symbol=i.symbol,timeframe_ns=tf) for tf in frames for i in instruments]
        with tempfile.TemporaryDirectory(prefix='public-walkforward-sign-',dir=scratch) as signing:
            signing=Path(signing);(signing/'key.der').write_bytes(bytes.fromhex('302e020100300506032b657004220420')+SEED)
            (signing/'openssl.cnf').write_bytes(b'')
            env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR') if k in os.environ};env['OPENSSL_CONF']=str(signing/'openssl.cnf')
            for index in range(12):
                check_cancel(cancel);origin=(index+1)*3*horizon_ns;bars=[]
                for tf in frames:
                    for k,instrument in enumerate(instruments):
                        for j in range(3):
                            t=origin-(3-j)*tf
                            bars.append(Bar(instrument,tf,t,t+tf,t+tf-1,t+tf,t+tf,origin,100.+j+k+(index+1)*.036+seed*.001,'VERIFIED',True,True,1,'fixture-grid',build_sha))
                        labels.append(dict(export_index=index,target=asdict(instrument),timeframe_ns=tf,label_end_ns=origin+horizon_ns,forward_log_return=.001*(k-1)))
                snapshot=Snapshot(tuple(bars),origin,epoch,('fixture-grid',)).validate()
                data=snapshot_bytes(snapshot);name=f'snapshot-{index:03d}.json';snapshot_sha=write(name,data)
                source=dict(source_id='public-fixture',engine='fixture',schema_sha256=SNAPSHOT_SCHEMA_SHA256,snapshot_id=f'immutable-synthetic-{index}',coherence_epoch_id=epoch,complete=True,first_availability_retained=True,revision_history_retained=True,event_watermark_ns=origin,availability_watermark_ns=origin)
                manifest=dict(version=1,producer_id='fixture-grid',producer_build_sha=build_sha,key_id='rfc-key',export_id=f'public-synthetic-{index}',coherence_epoch_id=epoch,snapshot_schema_version=1,snapshot_schema_sha256=SNAPSHOT_SCHEMA_SHA256,snapshot_sha256=snapshot_sha,snapshot_bytes=len(data),row_count=len(bars),knowledge_cutoff_ns=origin,issued_at_ns=origin+1,scope='SYNTHETIC_ENGINEERING_ONLY',partitions=partitions,sources=[source])
                message=SIGNATURE_DOMAIN+canonical_bytes(manifest);(signing/'message').write_bytes(message)
                subprocess.run([str(executable),'pkeyutl','-sign','-rawin','-keyform','DER','-inkey',str(signing/'key.der'),'-in',str(signing/'message'),'-out',str(signing/'signature')],cwd=signing,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=True,shell=False)
                check_cancel(cancel);signature=(signing/'signature').read_bytes();verifier.verify(PUBLIC,message,signature)
                manifest['signature_b64']=base64.b64encode(signature).decode();manifest_name=f'manifest-{index:03d}.json';manifest_sha=write(manifest_name,canonical_bytes(manifest))
                policy=dict(producer_id='fixture-grid',coherence_epoch_id=epoch,knowledge_cutoff_ns=origin,verification_ns=origin+10,scope='SYNTHETIC_ENGINEERING_ONLY',sources=[{k:source[k] for k in ('source_id','engine','schema_sha256')}],partitions=partitions)
                exports.append(dict(manifest_path=manifest_name,manifest_sha256=manifest_sha,snapshot_path=name,policy=policy))
        # This random bootstrap is only an engineering input; folds instantiate
        # fresh models and never warm-start from it or from an earlier fold.
        torch.manual_seed(seed)
        checkpoint_sha=save_checkpoint(build_structural_model(config),stage/'checkpoint.json',dataset_sha256=sha256(b'PUBLIC_SYNTHETIC_UNTRAINED_BOOTSTRAP').hexdigest(),seed=seed)
        h=horizon_ns
        payload=dict(version=1,scope='SYNTHETIC_ENGINEERING_ONLY',label_contract='PINNED_SYNTHETIC_LOG_RETURNS_V1',exports=exports,labels=labels,config=asdict(config),folds=[[10*h,20*h,28*h],[20*h,30*h,40*h]],holdout_symbols=[instruments[-1].symbol],steps=1,seed=seed,fee_bps=2.,slippage_bps=1.,embargo_ns=0,allow_retraining_on_prior_oos=True)
        source_sha=write('walkforward.json',canonical_bytes(payload))
        write('README.txt',b'PUBLIC SYNTHETIC ENGINEERING ONLY. Public RFC8032 test key is not real producer or owner authority. Direct labels are synthetic caller-pinned fixtures, not signed market labels. Random bootstrap is not trained; every fold trains fresh. Funding event history is absent; real OOS, physical G1 and trading are blocked. No network, DB or services required.\n')
        check_cancel(cancel)
        if target.exists() or target.is_symlink():raise ValueError('fixture output exists')
        os.rename(stage,target)
    return dict(status='PREPARED_PUBLIC_SYNTHETIC_WALKFORWARD',source_path=str(target/'walkforward.json'),source_sha256=source_sha,trust_store_path=str(target/'trust.json'),trust_store_sha256=trust_sha,checkpoint_path=str(target/'checkpoint.json'),checkpoint_sha256=checkpoint_sha,physical_g1='NOT_AUTHORIZED',real_oos='BLOCKED')
