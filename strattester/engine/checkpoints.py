from dataclasses import dataclass
import json

@dataclass(frozen=True)
class Checkpoint:
    job_id:str
    config_hash:str
    strategy_fingerprint:str|None
    cursor:str

def checkpoint_compatible(cp:Checkpoint,config_hash:str,strategy_fingerprint:str|None)->bool:
    return cp.config_hash==config_hash and cp.strategy_fingerprint==strategy_fingerprint

def encode_checkpoint(cp:Checkpoint)->str:
    return json.dumps({
        'job_id':cp.job_id,'config_hash':cp.config_hash,
        'strategy_fingerprint':cp.strategy_fingerprint,'cursor':cp.cursor
    },sort_keys=True,separators=(',',':'))

def decode_checkpoint(raw:str)->Checkpoint:
    data=json.loads(raw)
    return Checkpoint(
        str(data['job_id']),str(data.get('config_hash') or ''),
        data.get('strategy_fingerprint'),str(data['cursor']))

def require_compatible_checkpoint(raw:str|None,job_id:str,config_hash:str,strategy_fingerprint:str|None):
    if not raw:
        return None
    cp=decode_checkpoint(raw)
    if cp.job_id!=job_id:
        raise RuntimeError('checkpoint belongs to another job')
    if not checkpoint_compatible(cp,config_hash,strategy_fingerprint):
        raise RuntimeError('checkpoint is incompatible with current config/strategy')
    return cp
