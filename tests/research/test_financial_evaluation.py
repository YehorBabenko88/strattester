import pytest
from strattester.research.financial_evaluation import Trade, evaluate_ledger, gaussian_scores, evaluate_controls


def test_literal_entry_exit_fees_and_terminal_liquidation():
    # Price doubles: 1 unit notional long earns +1 simple return less both legs.
    report=evaluate_ledger([Trade('BTC',0,10,1.,1)],fee_bps=10,slippage_bps=10)
    assert report['returns']==pytest.approx([.996])
    assert report['turnover']==2
    assert report['mean']==pytest.approx(.996)


def test_positions_across_disjoint_labels_pay_entry_and_exit_each_time():
    report=evaluate_ledger([Trade('BTC',0,10,0.,1),Trade('BTC',20,30,0.,1)],fee_bps=10)
    assert report['returns']==pytest.approx([-.002,-.002])


def test_overlapping_labels_or_invalid_costs_are_rejected():
    with pytest.raises(ValueError):evaluate_ledger([Trade('BTC',0,10,.1,1),Trade('BTC',5,15,.1,-1)])
    with pytest.raises(ValueError):evaluate_ledger([Trade('BTC',0,10,.1,1)],fee_bps=float('nan'))


def test_distribution_score_and_randomized_controls_are_reproducible():
    report=gaussian_scores([0.,0.],[1.,1.],[0.,0.])
    assert report['nll']==pytest.approx(.9189385332046727)
    args=([[0.],[1.],[2.],[3.]],[.1,-.1,.2,-.2],[[4.],[5.]], [.2,-.2])
    a=evaluate_controls(*args,seed=3)
    assert a==evaluate_controls(*args,seed=3)
    assert set(a)=={'zero','mean','persistence','linear','random_signal','label_shuffle','delayed_feature'}
