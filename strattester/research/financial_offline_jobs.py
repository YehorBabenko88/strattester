"""Lazy bounded offline jobs and restartable immutable directory publication.

Only a caller-owned, access-controlled scratch directory is supported. This is
software recovery, not native Windows confinement or power-loss durability.
"""
from dataclasses import dataclass,asdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from .financial_contract import digest,integer
from .financial_snapshot import reject_linked_path,verified_bytes,canonical_bytes
from .financial_attested_inference import run_attested_offline
from .financial_training import TrainingCancelled

# Hard per-request input limits: snapshot8MiB+checkpoint8MiB+manifest256KiB+
# trust64KiB, rounded UP. Conservative charging prevents stat/growth races.
MAX_REQUEST_BYTES=17*1024*1024


@dataclass(frozen=True)
class OfflineJob:
    request: object
    policy: object


def stream_offline_jobs(jobs,*,verifier,max_requests=32,max_input_bytes=512*1024*1024,
                        max_work_bytes=512*1024*1024,cancel=lambda:False,output_root=None):
    integer(max_requests,'max_requests',1);integer(max_input_bytes,'max_input_bytes',1)
    if max_requests>256 or max_input_bytes>MAX_REQUEST_BYTES*256:raise ValueError('stream budget ceiling')
    iterator=iter(jobs);charged=0
    for index in range(max_requests+1):
        if cancel():raise TrainingCancelled('cancelled before next offline input')
        try:job=next(iterator)
        except StopIteration:return
        if index==max_requests:raise ValueError('offline request budget exceeded')
        if type(job) is not OfflineJob:raise ValueError('typed offline job required')
        charged+=MAX_REQUEST_BYTES
        if charged>max_input_bytes:raise ValueError('cumulative offline input budget exceeded')
        result=run_attested_offline(job.request,policy=job.policy,verifier=verifier,max_work_bytes=max_work_bytes,cancel=cancel)
        if cancel():raise TrainingCancelled('cancelled before offline result publication')
        if output_root is not None:
            r=job.request
            job_id=sha256(canonical_bytes({'version':1,'manifest':r.manifest_sha256,'checkpoint':r.checkpoint_sha256,
                'trust':r.trust_store_sha256,'policy':asdict(job.policy),'instrument':asdict(r.instrument),
                'timeframe':r.timeframe_ns,'horizon':r.horizon_ns,'available':r.available_ns,
                'verifier':verifier.executable_sha256,'model_config':result.provenance['model_config']})).hexdigest()
            publish_result(output_root,job_id,asdict(result))
        yield result


def _bounded_json_bytes(payload):
    stack=[(payload,0)];nodes=0
    while stack:
        value,depth=stack.pop();nodes+=1
        if nodes>8192 or depth>32:raise ValueError('result object budget')
        if type(value) is dict:
            if len(value)>256 or any(type(k) is not str or len(k)>256 for k in value):raise ValueError('result mapping budget')
            stack.extend((v,depth+1) for v in value.values())
        elif type(value) in (list,tuple):
            if len(value)>512:raise ValueError('result sequence budget')
            stack.extend((v,depth+1) for v in value)
        elif type(value) is str:
            if len(value)>4096:raise ValueError('result string budget')
        elif value is not None and type(value) not in (bool,int,float):raise ValueError('result JSON type')
        elif type(value) is float and not math.isfinite(value):raise ValueError('nonfinite result')
    encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False)
    chunks=[];size=0
    for text in encoder.iterencode(payload):
        chunk=text.encode('utf-8');size+=len(chunk)
        if size>1024*1024:raise ValueError('result byte budget')
        chunks.append(chunk)
    return b''.join(chunks)


def publish_result(output_root,job_identity,payload):
    """Recompute payload before replay; never trust a cached colocated checksum.

    An abrupt process exit leaves a complete stage or an atomic final directory.
    Restart promotes only a stage whose bytes equal the newly computed result.
    Partial/mismatched stages are preserved in a bounded cleanup manifest.
    """
    digest(job_identity)
    data=_bounded_json_bytes({'version':1,'job_identity':job_identity,'physical_g1':'NOT_AUTHORIZED','result':payload})
    expected=sha256(data).hexdigest();root=reject_linked_path(output_root)
    if not root.is_dir():raise ValueError('existing owned output directory required')
    entries=[]
    for path in root.iterdir():
        if len(entries)>=64:raise ValueError('publication entry budget; owner cleanup required')
        entries.append(path)
    final=root/job_identity
    def valid(directory):
        reject_linked_path(directory)
        if not directory.is_dir():raise ValueError('result directory required')
        names=[]
        for entry in directory.iterdir():
            names.append(entry.name)
            if len(names)>1:raise ValueError('unexpected result directory membership')
        if names!=['result.json']:raise ValueError('partial result directory')
        verified_bytes(directory/'result.json',expected,1024*1024)
    def receipt(status):
        stages=[str(p) for p in root.iterdir() if p.name.startswith('.stage-')]
        return {'status':status,'job_identity':job_identity,'path':str(final/'result.json'),
                'sha256':expected,'preserved_stages':stages,'physical_g1':'NOT_AUTHORIZED'}
    if final.exists() or final.is_symlink():
        valid(final);return receipt('REPLAY_VERIFIED')
    stage=None;recovered=False
    for candidate in entries:
        if not candidate.name.startswith('.stage-'+job_identity+'-'):continue
        try:valid(candidate)
        except (ValueError,OSError):continue
        stage=candidate;recovered=True;break
    if stage is None:
        stage=Path(tempfile.mkdtemp(prefix='.stage-'+job_identity+'-',dir=root))
        with (stage/'result.json').open('xb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
    # Directory rename publishes all bytes together and creates no hardlink
    # alias. Existing nonempty final directories are never replaced.
    try:os.rename(stage,final)
    except OSError:
        if final.exists():valid(final);return receipt('REPLAY_VERIFIED')
        raise
    valid(final)
    return receipt('RECOVERED' if recovered else 'PUBLISHED')
