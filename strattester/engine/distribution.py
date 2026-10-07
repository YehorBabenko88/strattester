from __future__ import annotations
from hashlib import sha256
from strattester.engine.jobs import Job,JobState

def _score(key:str,node_id:str)->int:
    raw=sha256(f'{key}|{node_id}'.encode('utf-8')).digest()
    return int.from_bytes(raw[:8],'big',signed=False)

def assign_node(key:str,node_ids):
    nodes=tuple(sorted({str(x) for x in node_ids if str(x)}))
    if not nodes:
        raise ValueError('at least one node is required')
    return max(nodes,key=lambda node:_score(str(key),node))

def assign_symbols(symbols,node_ids):
    nodes=tuple(node_ids)
    return {str(symbol):assign_node(str(symbol),nodes) for symbol in symbols}

def make_sync_jobs(symbols,node_ids):
    assignments=assign_symbols(symbols,node_ids)
    return tuple(Job.new('sync',symbol=symbol,target_node=node,resource_key=f'market:{node}:{symbol}',state=JobState.READY) for symbol,node in sorted(assignments.items()))

def make_backtest_jobs(symbols,node_ids,strategy_ids,*,strategy_version=None,config_hash=''):
    assignments=assign_symbols(symbols,node_ids)
    jobs=[]
    for symbol,node in sorted(assignments.items()):
        for strategy_id in sorted({str(x) for x in strategy_ids}):
            jobs.append(Job.new('backtest',symbol=symbol,strategy_id=strategy_id,strategy_version=strategy_version,config_hash=config_hash,target_node=node,state=JobState.READY))
    return tuple(jobs)

def reassign_unavailable(job,available_node_ids):
    available=tuple(available_node_ids)
    if job.target_node in set(available):
        return job
    node=assign_node(job.symbol or job.id,available)
    resource_key=(f'market:{node}:{job.symbol}' if job.job_type=='sync' and job.symbol else job.resource_key)
    return job.with_state(JobState.RETRYABLE,target_node=node,resource_key=resource_key,lease_owner=None,lease_until=None,error='target node unavailable; reassigned')
