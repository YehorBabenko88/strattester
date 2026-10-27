import pytest
from decimal import Decimal
from research.independent_ledger_oracle import independent_roundtrip_ledger

def test_costs_reduce_long_and_short_pnl():
    rows = [('BTCUSDT',0,10,'0.02',1), ('ETHUSDT',0,10,'-0.03',-1)]
    gross = independent_roundtrip_ledger(rows)
    net = independent_roundtrip_ledger(rows,fee_bps=5,slippage_bps=3,funding_bps=2)
    assert all(n < g for n,g in zip(net,gross))
    assert net[0] == Decimal('0.0182')
    assert net[1] == Decimal('0.0282')

def test_disjoint_roundtrip_boundary_and_overlap():
    assert len(independent_roundtrip_ledger([('BTC',0,10,.01,1),('BTC',10,20,.02,1)])) == 2
    with pytest.raises(ValueError):
        independent_roundtrip_ledger([('BTC',0,10,.01,1),('BTC',9,20,.02,1)])

def test_invalid_costs_and_position_fail_closed():
    with pytest.raises(ValueError):
        independent_roundtrip_ledger([('BTC',0,10,.01,2)])
    with pytest.raises(ValueError):
        independent_roundtrip_ledger([('BTC',0,10,.01,1)],fee_bps=-1)


def test_zero_position_has_zero_costs():
    assert independent_roundtrip_ledger([('BTC',0,10,.05,0)],fee_bps=10,slippage_bps=10,funding_bps=10) == (Decimal('0.00'),)
