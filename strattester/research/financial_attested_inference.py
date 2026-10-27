"""Explicit attested-export inference; no SyncEngine/store/client/order capability."""
from dataclasses import dataclass
from pathlib import Path
from .financial_contract import Instrument,integer,digest
from .financial_snapshot import verified_bytes,bounded_json
from .financial_signed_export import load_attested_export
from .financial_checkpoint import load_checkpoint
from .financial_pipeline import predict_snapshot
from .financial_training import TrainingCancelled


@dataclass(frozen=True)
class AttestedInferenceRequest:
    manifest_path: Path
    manifest_sha256: str
    snapshot_path: Path
    checkpoint_path: Path
    checkpoint_sha256: str
    trust_store_path: Path
    trust_store_sha256: str
    instrument: Instrument
    timeframe_ns: int
    horizon_ns: int
    available_ns: int

    def validate(self):
        for value in (self.manifest_sha256,self.checkpoint_sha256,self.trust_store_sha256):digest(value)
        self.instrument.validate()
        for name in ('timeframe_ns','horizon_ns','available_ns'):integer(getattr(self,name),name,1)
        if self.horizon_ns%self.timeframe_ns:raise ValueError('unaligned forecast horizon')
        return self


@dataclass(frozen=True)
class OfflineInferenceResult:
    prediction: object
    provenance: dict


def run_attested_offline(request,*,policy,verifier,max_work_bytes=512*1024*1024,cancel=lambda:False):
    def check():
        if cancel():raise TrainingCancelled('cancelled offline inference')
    check();request.validate();policy.validate();integer(max_work_bytes,'job work budget',1)
    if not 16*1024*1024<=max_work_bytes<=1024*1024*1024:raise ValueError('job memory budget')
    if not policy.verification_ns<=request.available_ns<policy.knowledge_cutoff_ns+request.horizon_ns:
        raise ValueError('forecast must be available inside its future horizon')
    export=load_attested_export(manifest_path=request.manifest_path,manifest_sha256=request.manifest_sha256,
        snapshot_path=request.snapshot_path,trust_store_path=request.trust_store_path,
        trust_store_sha256=request.trust_store_sha256,policy=policy,verifier=verifier,cancel=cancel)
    check()
    checkpoint_data=verified_bytes(request.checkpoint_path,request.checkpoint_sha256,8*1024*1024)
    payload=bounded_json(checkpoint_data)
    from .financial_structural_model import StructuralConfig
    try:config=StructuralConfig(**payload['config']).validate()
    except (KeyError,TypeError) as exc:raise ValueError('checkpoint config') from exc
    # Bounded serialized buffers plus conservative JSON/object copies. This is
    # software admission, not a claim of OS hard RSS enforcement.
    serialized=export.provenance['snapshot_bytes']+export.provenance['manifest_bytes']+len(checkpoint_data)+64*1024
    admitted=config.max_work_bytes+serialized*16
    if admitted>max_work_bytes:raise ValueError('aggregate inference memory budget')
    check();model,metadata=load_checkpoint(request.checkpoint_path,request.checkpoint_sha256)
    check()
    prediction=predict_snapshot(export.snapshot,model,instrument=request.instrument,timeframe_ns=request.timeframe_ns,
        horizon_ns=request.horizon_ns,model_sha256=request.checkpoint_sha256,available_ns=request.available_ns)
    check()
    return OfflineInferenceResult(prediction,{**export.provenance,'checkpoint_sha256':request.checkpoint_sha256,
        'training_dataset_sha256':metadata['dataset_sha256'],'model_config':metadata['config'],
        'admitted_work_bytes':admitted,'serialized_input_bytes':serialized,
        'trading':'NO-GO','physical_g1':'NOT_AUTHORIZED'})
