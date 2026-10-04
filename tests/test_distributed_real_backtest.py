from pathlib import Path
from strattester.grid_bridge import make_manifest,aggregate_fingerprint
from strattester.grid_worker import _execute
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle


def _seed(path,symbols):
    store=SQLiteMarketStore.open(path)
    try:
        for symbol in symbols:
            rows=[]
            for i in range(121):
                base=100.0+(i%17)*0.2
                rows.append(Candle(symbol,"1m",i*60_000,base,base+1.0,base-1.0,
                    base+(0.25 if i%2 else -0.25),10.0+i,1000.0+i,True))
            assert store.upsert_candles(rows).accepted==121
    finally:
        store.close()


def _payload(db,results,symbol,shard_id):
    spec={"local_market_db":str(db),"local_results_db":str(results),
          "strategy":"legacy_grid","symbol":symbol,"start_ms":0,"end_ms":120*60_000}
    return {"research_run_id":"run-determinism","research_shard_id":shard_id,
            "job_type":"strategy_backtest","dataset_hash":"dataset-fixed",
            "strattester_version":"test-v1","config":{},"input_spec":spec}


def _manifest(payload,result,metrics):
    return make_manifest(run_id=payload["research_run_id"],
        job_id=payload["research_shard_id"],job_type=payload["job_type"],
        dataset_hash=payload["dataset_hash"],code_version=payload["strattester_version"],
        config=payload["config"],input_spec=payload["input_spec"],
        result=result,metrics=metrics)


def test_real_strategy_backtest_is_stable_across_independent_worker_stores(tmp_path):
    symbols=("BTCUSDT","ETHUSDT")
    db_a=tmp_path/"worker-a.db";db_b=tmp_path/"worker-b.db"
    _seed(db_a,symbols);_seed(db_b,symbols)

    local=[]
    for n,symbol in enumerate(symbols):
        payload=_payload(db_a,tmp_path/f"local-{n}.db",symbol,f"shard-{n}")
        result,metrics=_execute({"payload":payload})
        local.append(_manifest(payload,result,metrics))

    distributed=[]
    for n,symbol in reversed(list(enumerate(symbols))):
        payload=_payload(db_b,tmp_path/f"remote-{n}.db",symbol,f"shard-{n}")
        result,metrics=_execute({"payload":payload})
        distributed.append(_manifest(payload,result,metrics))

    by_id_local={m["job_id"]:m for m in local}
    by_id_remote={m["job_id"]:m for m in distributed}
    assert set(by_id_local)==set(by_id_remote)
    for shard_id in by_id_local:
        assert by_id_local[shard_id]["result"]==by_id_remote[shard_id]["result"]
        assert by_id_local[shard_id]["metrics"]==by_id_remote[shard_id]["metrics"]
        assert by_id_local[shard_id]["result_hash"]==by_id_remote[shard_id]["result_hash"]
        assert by_id_local[shard_id]["input_hash"]==by_id_remote[shard_id]["input_hash"]
    assert aggregate_fingerprint(local)==aggregate_fingerprint(distributed)
