import pytest
from strattester.research.execution import ExecutionPolicy, Signal, ScaleSignal, simulate_trade, simulate_scale_trade


def test_single_trade_fails_closed_on_empty_bars():
    signal=Signal(0,"long","market",None,90.0,110.0)
    with pytest.raises(ValueError,match="empty bars"):
        simulate_trade(signal,[],ExecutionPolicy(bar_ms=60000))


def test_limit_trade_requires_entry_price():
    signal=Signal(0,"long","limit",None,90.0,110.0)
    with pytest.raises(ValueError,match="limit entry_price"):
        simulate_trade(signal,[],ExecutionPolicy(bar_ms=60000))


def test_invalid_execution_policy_rejected():
    signal=Signal(0,"long","market",None,90.0,110.0)
    for policy in (ExecutionPolicy(bar_ms=0),ExecutionPolicy(bar_ms=60000,fee_rate=-0.1),
                   ExecutionPolicy(bar_ms=60000,slippage_bps=-1.0),
                   ExecutionPolicy(bar_ms=60000,position_usd=0)):
        with pytest.raises(ValueError,match="execution policy"):
            simulate_trade(signal,[],policy)


def test_scale_trade_fails_closed_on_empty_bars():
    signal=ScaleSignal(0,"long",((100.0,1.0),),90.0,((110.0,1.0),))
    with pytest.raises(ValueError,match="empty bars"):
        simulate_scale_trade(signal,[],ExecutionPolicy(bar_ms=60000))
