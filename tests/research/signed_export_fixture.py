"""Public RFC test key only. No private production credentials."""
import base64
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
from strattester.research.financial_contract import Instrument,Bar,Snapshot
from strattester.research.financial_snapshot import canonical_bytes,snapshot_bytes
from strattester.research.financial_checkpoint import save_checkpoint
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model

PUBLIC=bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
SEED=bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb')

def bundle(root,*,symbol='BTCUSDT',market='linear',tf=60_000_000_000):
    from strattester.research.financial_signatures import OpenSSLVerifier
    from strattester.research.financial_signed_export import ExportPolicy,SourceIdentity,MarketPartition,SNAPSHOT_SCHEMA_SHA256,SIGNATURE_DOMAIN
    root.mkdir(exist_ok=True)
    exe=Path(shutil.which('openssl') or 'C:/Program Files/Git/usr/bin/openssl.exe').resolve();assert exe.is_file()
    verifier=OpenSSLVerifier(exe,sha256(exe.read_bytes()).hexdigest(),root)
    trust=dict(version=1,keys=[dict(producer_id='fixture-grid',key_id='rfc-key',public_key_b64=base64.b64encode(PUBLIC).decode(),valid_from_ns=0,valid_until_ns=10**20,revoked=False)])
    trust_data=canonical_bytes(trust);(root/'trust.json').write_bytes(trust_data)
    instrument=Instrument('bybit',market,symbol);origin=6*tf
    bars=tuple(Bar(instrument,tf,t,t+tf,t+tf-1,t+tf,t+tf,origin,100.+i,'VERIFIED',True,True,1,'fixture-grid','a'*40) for i,t in enumerate(range(3*tf,6*tf,tf)))
    snapshot=Snapshot(bars,origin,'epoch-fixture',('fixture-grid',));data=snapshot_bytes(snapshot);(root/'snapshot.json').write_bytes(data)
    partition=dict(exchange=instrument.exchange,market_type=market,symbol=symbol,timeframe_ns=tf)
    manifest=dict(version=1,producer_id='fixture-grid',producer_build_sha='a'*40,key_id='rfc-key',export_id='fixture-export',coherence_epoch_id='epoch-fixture',snapshot_schema_version=1,snapshot_schema_sha256=SNAPSHOT_SCHEMA_SHA256,snapshot_sha256=sha256(data).hexdigest(),snapshot_bytes=len(data),row_count=len(bars),knowledge_cutoff_ns=origin,issued_at_ns=origin+1,scope='SYNTHETIC_ENGINEERING_ONLY',
        partitions=[partition],sources=[dict(source_id='fixture-source',engine='fixture',schema_sha256='b'*64,snapshot_id='immutable-cut-1',coherence_epoch_id='epoch-fixture',complete=True,first_availability_retained=True,revision_history_retained=True,event_watermark_ns=origin,availability_watermark_ns=origin)])
    def publish(manifest):
        unsigned={k:v for k,v in manifest.items() if k!='signature_b64'}
        (root/'sign-message').write_bytes(SIGNATURE_DOMAIN+canonical_bytes(unsigned))
        (root/'test-key.der').write_bytes(bytes.fromhex('302e020100300506032b657004220420')+SEED)
        subprocess.run([str(exe),'pkeyutl','-sign','-rawin','-keyform','DER','-inkey',str(root/'test-key.der'),'-in',str(root/'sign-message'),'-out',str(root/'test-signature')],check=True,capture_output=True)
        manifest={**unsigned,'signature_b64':base64.b64encode((root/'test-signature').read_bytes()).decode()}
        contents=canonical_bytes(manifest);(root/'manifest.json').write_bytes(contents)
        return sha256(contents).hexdigest()
    manifest_sha=publish(manifest)
    policy=ExportPolicy('fixture-grid','epoch-fixture',origin,(SourceIdentity('fixture-source','fixture','b'*64),),(MarketPartition(**partition),),verification_ns=origin+10)
    model=build_structural_model(StructuralConfig(horizon_ns=tf*2,recycles=0))
    model_sha=save_checkpoint(model,root/'checkpoint.json',dataset_sha256=sha256(data).hexdigest(),seed=0)
    return dict(root=root,verifier=verifier,manifest=manifest,manifest_sha=manifest_sha,policy=policy,publish=publish,trust_sha=sha256(trust_data).hexdigest(),snapshot=snapshot,checkpoint_sha=model_sha,instrument=instrument,tf=tf)
