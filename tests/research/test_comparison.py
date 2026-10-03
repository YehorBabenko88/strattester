from strattester.research.comparison import strategy_summary

def test_strategy_summary_projects_common_backtest_metrics():
    rows=[{'symbol':'BTCUSDT','strategy_id':'smc','strategy_version':'1',
           'metrics':{'output':{'metrics':{'trades':4,'net_pnl':3.5,'profit_factor':1.8,
             'max_drawdown':1.2,'win_rate':.5,'expectancy':.875}}}}]
    x=strategy_summary(rows)[0]
    assert x['symbol']=='BTCUSDT' and x['trades']==4
    assert x['net_pnl']==3.5 and x['profit_factor']==1.8
