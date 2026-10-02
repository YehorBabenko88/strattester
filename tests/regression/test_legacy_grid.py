from strattester.strategies.builtin.legacy_grid import BacktestConfig,close_trade
def test_long_tp_math_includes_both_side_fees():
    c=BacktestConfig(); t=close_trade('LONG',100,101.5,'TP',c)
    assert round(t.gross_pnl,8)==1.5
    assert round(t.fees,8)==round((100+101.5)*c.taker_fee,8)
    assert t.net_pnl<t.gross_pnl
def test_short_sl_math():
    t=close_trade('SHORT',100,101,'SL')
    assert round(t.gross_pnl,8)==-1.0 and t.reason=='SL'
