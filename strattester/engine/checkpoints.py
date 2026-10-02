from dataclasses import dataclass
@dataclass(frozen=True)
class Checkpoint:
    job_id:str
    config_hash:str
    strategy_fingerprint:str|None
    cursor:str
def checkpoint_compatible(cp:Checkpoint,config_hash:str,strategy_fingerprint:str|None)->bool:
    return cp.config_hash==config_hash and cp.strategy_fingerprint==strategy_fingerprint
