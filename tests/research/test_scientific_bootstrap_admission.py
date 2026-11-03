from strattester.marketdata.sqlite_store import Candle, SQLiteMarketStore
from strattester.research.scientific_bootstrap import build_symbol_science, export_scientific_bootstrap


def candles(store, symbol='BTCUSDT', count=60):
    store.upsert_candles([Candle(symbol, '1m', i*60000, 10, 11, 9, 10, 1) for i in range(count)])


def test_candles_alone_never_claim_full_scientific_capabilities(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store)
        row=build_symbol_science(store, 'BTCUSDT', 0, 59*60000)
        assert row['status']=='PARTIAL'
        assert row['dataset_evidence']['candles']['coverage_complete'] is True
        assert row['dataset_evidence']['funding']['count']==0
        bundle=export_scientific_bootstrap(store, ['BTCUSDT'], tmp_path/'science.json', 0, 59*60000)
        assert bundle['status']=='PARTIAL'
        assert bundle['capabilities']['funding'] is False
        assert bundle['capabilities']['open_interest'] is False
        assert bundle['capabilities']['public_trade_aggregates'] is False
        assert bundle['live_promotion_allowed'] is False
    finally:store.close()


def test_sparse_or_other_symbol_rows_do_not_establish_coverage(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store)
        candles(store, 'ETHUSDT')
        store.upsert_open_interest('ETHUSDT', [{'timestamp':0, 'openInterest':10}])
        store.upsert_funding('BTCUSDT', [{'fundingRateTimestamp':0, 'fundingRate':0.0001}])
        row=build_symbol_science(store,'BTCUSDT',0,59*60000)
        assert row['status']=='PARTIAL'
        assert row['dataset_evidence']['open_interest']['count']==0
        funding=row['dataset_evidence']['funding']
        assert funding['count']==1 and funding['coverage_complete'] is False
        assert funding['provenance']=='LOCAL_STORED_ROWS_NOT_EXCHANGE_ATTESTATION'
        assert len(funding['sha256'])==64
    finally:store.close()


def test_gaps_and_requested_empty_symbols_fail_closed(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store, count=61)
        store.connection.execute("DELETE FROM candles WHERE open_time=60000")
        store.connection.commit()
        row=build_symbol_science(store,'BTCUSDT',0,60*60000)
        assert row['status']!='READY'
        assert row['dataset_evidence']['candles']['coverage_complete'] is False
        bundle=export_scientific_bootstrap(store,[],tmp_path/'empty.json')
        assert bundle['status']=='BLOCKED'
        assert not any(bundle['capabilities'].values())
    finally:store.close()


def test_thirty_candles_are_insufficient_for_nonlinear_science(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store,count=30)
        assert build_symbol_science(store,'BTCUSDT')['status']=='INSUFFICIENT'
    finally:store.close()


def test_sharded_store_export_uses_coherent_local_rows(tmp_path):
    from strattester.marketdata.sharded_store import ShardedMarketStore
    store=ShardedMarketStore(tmp_path/'shards')
    try:
        candles(store)
        bundle=export_scientific_bootstrap(store,['BTCUSDT'],tmp_path/'sharded.json')
        assert bundle['symbols'][0]['dataset_evidence']['candles']['coverage_complete']
        assert bundle['status']=='PARTIAL'
    finally:store.close()


def test_dense_aggregates_cannot_attest_complete_event_history(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store)
        store.upsert_public_trade_aggregates('BTCUSDT',[{'open_time':i*60000,'trade_count':1,
                                  'buy_volume':1,'sell_volume':1} for i in range(60)])
        evidence=build_symbol_science(store,'BTCUSDT')['dataset_evidence']['public_trade_aggregates']
        assert evidence['count']==60
        assert evidence['coverage_complete'] is False
        assert evidence['reason']=='EVENT_HISTORY_CONTRACT_UNAVAILABLE'
    finally:store.close()


def test_actual_fixed_grid_datasets_have_independent_capabilities(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store)
        for dataset in ('mark_price','index_price','premium_index'):
            store.upsert_price_klines(dataset,'BTCUSDT',[[i*60000,10,11,9,10] for i in range(60)])
        store.upsert_open_interest('BTCUSDT',[{'timestamp':i*300000,'openInterest':10} for i in range(12)])
        store.upsert_long_short_ratio('BTCUSDT',[{'timestamp':i*300000,'buyRatio':0.6,'sellRatio':0.4} for i in range(12)])
        bundle=export_scientific_bootstrap(store,['BTCUSDT'],tmp_path/'science.json')
        for dataset in ('candles','mark_price','index_price','premium_index','open_interest','long_short_ratio'):
            assert bundle['capabilities'][dataset] is True
        assert bundle['capabilities']['funding'] is False
        assert bundle['capabilities']['public_trade_aggregates'] is False
        assert bundle['status']=='PARTIAL'
    finally:store.close()


def test_funding_evidence_keeps_actual_irregular_event_window(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store)
        store.upsert_funding('BTCUSDT',[{'fundingRateTimestamp':123456,'fundingRate':0.0001}])
        first=build_symbol_science(store,'BTCUSDT')['dataset_evidence']['funding']
        assert first['count']==1 and first['earliest']==123456
        store.connection.execute('UPDATE funding SET rate=0.0002')
        store.connection.commit()
        second=build_symbol_science(store,'BTCUSDT')['dataset_evidence']['funding']
        assert first['sha256']!=second['sha256']
        assert second['coverage_complete'] is False
    finally:store.close()


def test_ten_requested_symbols_cannot_borrow_one_symbols_coverage(tmp_path):
    symbols=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT',
             'BNBUSDT','ADAUSDT','AVAXUSDT','DOTUSDT','LINKUSDT']
    store=SQLiteMarketStore.open(tmp_path/'market.sqlite3')
    try:
        candles(store)
        bundle=export_scientific_bootstrap(store,symbols,tmp_path/'ten.json',0,59*60000)
        assert len(bundle['symbols'])==10 and bundle['status']=='PARTIAL'
        assert bundle['capabilities']['candles'] is False
        rows={row['symbol']:row for row in bundle['symbols']}
        assert rows['BTCUSDT']['samples']==60
        assert all(rows[s]['samples']==0 and rows[s]['status']=='INSUFFICIENT' for s in symbols[1:])
    finally:store.close()
