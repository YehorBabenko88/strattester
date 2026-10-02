from strattester.marketdata.sqlite_store import SQLiteMarketStore

def test_public_trade_aggregates_are_idempotent_and_iterable(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    rows=[
      {'open_time':0,'buy_volume':3,'sell_volume':7,'turnover':1000,'trade_count':4,'vwap':100,'max_trade':5},
      {'open_time':60_000,'buy_volume':8,'sell_volume':2,'turnover':1100,'trade_count':5,'vwap':101,'max_trade':4},
    ]
    a=s.upsert_public_trade_aggregates('BTCUSDT',rows,'1m')
    b=s.upsert_public_trade_aggregates('BTCUSDT',rows,'1m')
    assert (a.accepted,b.unchanged)==(2,2)
    got=list(s.iter_public_trade_aggregates('BTCUSDT','1m'))
    assert got[0]['delta']==-4
    assert got[1]['delta']==6
    s.close()
