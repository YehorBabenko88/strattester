from strattester.runtime.bootstrap_worker import build_worker
def test_worker_bootstrap_has_durable_state(tmp_path):
    b,state,runtime=build_worker(tmp_path,lambda job:None)
    assert b.state_db.exists()
    assert runtime.state_store is state
    state.close()

from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_worker_bootstrap_wires_background_migration_for_existing_market_db(tmp_path):
    data=tmp_path/'data'; data.mkdir()
    market=data/'bybit_1m.sqlite3'
    store=SQLiteMarketStore.open(market)
    store.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1)])
    store.close()
    b,state,runtime=build_worker(tmp_path,lambda job:None)
    assert len(runtime.background_tasks)==1
    symbols=list(runtime.background_tasks[0].symbol_provider())
    assert symbols==['BTCUSDT']
    state.close()
