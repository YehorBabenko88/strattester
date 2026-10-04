from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
from strattester.grid_bridge import make_manifest,digest,input_digest
from strattester.marketdata.bybit_client import BybitClient
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.persistence.result_store import ResultStore
from strattester.research.runner import ResearchRunner
from strattester.strategies.registry import builtin_registry


def _definition(strategy_id):
    matches=[d for d in builtin_registry().discover() if d.enabled and d.id==strategy_id]
    if not matches: raise ValueError(f"unknown or disabled strategy: {strategy_id}")
    if len(matches)>1: raise ValueError(f"ambiguous strategy id: {strategy_id}")
    return matches[0]


def _execute(job):
    payload=dict(job.get("payload") or job)
    spec=dict(payload.get("input_spec") or {})
    job_type=str(payload.get("job_type") or "")
    if job_type=="probe":
        # Protocol-level probe must be deterministic across machines/processes.
        # Runtime diagnostics such as PID belong in logs/heartbeat, never in result_hash.
        return {"probe":spec},{}

    if job_type=="history_sync":
        raise ValueError("history_sync is Grid-owned for distributed runs")
    if job_type!="strategy_backtest":
        raise ValueError(f"unsupported Grid job_type: {job_type}")

    db_path=Path(spec["local_market_db"])
    db_path.parent.mkdir(parents=True,exist_ok=True)
    store=SQLiteMarketStore.open(db_path)
    client=BybitClient()
    try:
        definition=_definition(str(spec["strategy"]))
        symbol=str(spec["symbol"])
        start_ms=int(spec["start_ms"]); end_ms=int(spec["end_ms"])
        instrument={"symbol":symbol,"launchTime":str(start_ms)}
        runner=ResearchRunner(store,client)
        results_path=Path(spec["local_results_db"])
        results_path.parent.mkdir(parents=True,exist_ok=True)
        results=ResultStore.open(results_path)
        try:
            r=runner.run(definition,instrument,start_ms=start_ms,end_ms=end_ms)
            metrics={"fingerprint":r.fingerprint,"output":r.output}
            results.put(str(payload["research_run_id"]),symbol,r.strategy_id,r.strategy_version,metrics)
            result={"symbol":symbol,"strategy_id":r.strategy_id,
                    "strategy_version":r.strategy_version,"fingerprint":r.fingerprint,
                    "output":r.output}
            return result,{"fingerprint":r.fingerprint}
        finally:
            results.close()
    finally:
        store.close()


def main(argv=None):
    p=argparse.ArgumentParser(prog="strattester-grid-worker")
    p.add_argument("--job",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    job=json.loads(a.job.read_text(encoding="utf-8"))
    payload=dict(job.get("payload") or job)
    config=dict(payload.get("config") or {})
    spec=dict(payload.get("input_spec") or {})

    if digest(config)!=str(payload.get("config_hash")):
        raise SystemExit("config hash mismatch before execution")
    if input_digest(spec)!=str(payload.get("input_hash")):
        raise SystemExit("input hash mismatch before execution")

    result,metrics=_execute(job)
    manifest=make_manifest(
        run_id=payload["research_run_id"],
        job_id=payload["research_shard_id"],
        job_type=payload["job_type"],
        dataset_hash=payload["dataset_hash"],
        code_version=payload["strattester_version"],
        config=config,input_spec=spec,result=result,metrics=metrics,
    )
    a.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=a.output.with_suffix(a.output.suffix+".tmp")
    tmp.write_text(json.dumps(manifest,sort_keys=True,default=str),encoding="utf-8")
    os.replace(tmp,a.output)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
