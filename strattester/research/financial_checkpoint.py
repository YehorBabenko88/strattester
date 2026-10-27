"""Bounded tensor-only JSON checkpoints: never pickle/torch.load/eval.

Caller supplies the trusted digest. A checksum stored alongside an untrusted
file does not establish trust. Completed artifacts are created exclusively.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from .financial_contract import digest, integer
from .financial_snapshot import canonical_bytes, verified_bytes, unique_object, bounded_json, reject_linked_path
from .financial_structural_model import StructuralConfig, build_structural_model


def model_fingerprint(model):
    import torch
    model.config.validate()
    records={}
    for name,tensor in model.state_dict().items():
        if tensor.dtype!=torch.float32 or tensor.device.type!='cpu' or not torch.isfinite(tensor).all():
            raise ValueError('checkpoint identity requires finite CPU float32 state')
        records[name]={'shape':list(tensor.shape),'values':tensor.detach().reshape(-1).tolist()}
    return sha256(canonical_bytes({'config':asdict(model.config),'tensors':records})).hexdigest()


def save_checkpoint(model, path, *, dataset_sha256, seed, max_bytes=8*1024*1024):
    import torch
    digest(dataset_sha256);integer(seed,'seed');integer(max_bytes,'max_bytes',1)
    model.config.validate()
    path=Path(path)
    reject_linked_path(path.parent)
    if path.exists() or path.is_symlink(): raise ValueError('checkpoint exists; refusing replay/overwrite')
    tensors={}
    for name,tensor in model.state_dict().items():
        if tensor.dtype!=torch.float32 or not torch.isfinite(tensor).all(): raise ValueError('checkpoint requires finite float32 tensors')
        tensors[name]={'shape':list(tensor.shape),'values':tensor.detach().cpu().reshape(-1).tolist()}
    payload={'version':1,'config':asdict(model.config),'dataset_sha256':dataset_sha256,'seed':seed,'tensors':tensors}
    data=canonical_bytes(payload)
    if len(data)>max_bytes: raise ValueError('checkpoint byte budget')
    # Exclusive creation prevents duplicate tasks from replacing an accepted
    # artifact. A partial write is removed, and never returned as registered.
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='wb',dir=path.parent,prefix='.checkpoint-',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        # Hard-link publication is atomic and exclusive on both Windows and
        # POSIX. A crash before publication leaves only an unregistered temp.
        try:os.link(temporary,path)
        except FileExistsError as exc:raise ValueError('checkpoint exists; refusing replay/overwrite') from exc
        temporary.unlink();temporary=None
        # Verify before returning a registered digest. If this fails, preserve
        # the unregistered final path for operator recovery: pathname unlink
        # after an inode check can race and delete an unrelated replacement.
        verified_bytes(path,sha256(data).hexdigest(),max_bytes)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return sha256(data).hexdigest()


def load_checkpoint(path, expected_sha256, *, max_bytes=8*1024*1024):
    import torch
    payload=bounded_json(verified_bytes(path,expected_sha256,max_bytes))
    if set(payload)!={'version','config','dataset_sha256','seed','tensors'} or type(payload['version']) is not int or payload['version']!=1:
        raise ValueError('checkpoint schema')
    digest(payload['dataset_sha256']);integer(payload['seed'],'seed')
    # Missing versions identify legacy equations; reject before constructing
    # any parameter tensors rather than silently changing checkpoint meaning.
    if not isinstance(payload['config'],dict) or 'model_equations_version' not in payload['config']:
        raise ValueError('checkpoint model equations version required')
    try: config=StructuralConfig(**payload['config']).validate()
    except (TypeError,AttributeError) as exc: raise ValueError('checkpoint config') from exc
    model=build_structural_model(config)
    expected=model.state_dict()
    if not isinstance(payload['tensors'],dict) or set(expected)!=set(payload['tensors']):raise ValueError('checkpoint tensor names')
    state={}
    for name,tensor in expected.items():
        record=payload['tensors'][name]
        if (not isinstance(record,dict) or set(record)!={'shape','values'}
            or type(record['shape']) is not list or any(type(v) is not int for v in record['shape'])
            or record['shape']!=list(tensor.shape) or type(record['values']) is not list
            or len(record['values'])!=tensor.numel()
            or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>3.4e38 for v in record['values'])):
            raise ValueError('checkpoint tensor shape/finite contract')
        state[name]=torch.tensor(record['values'],dtype=torch.float32).reshape(tensor.shape)
    model.load_state_dict(state,strict=True);model.eval()
    model.checkpoint_identity=(expected_sha256,model_fingerprint(model))
    return model,{key:payload[key] for key in ('dataset_sha256','seed','config')}
