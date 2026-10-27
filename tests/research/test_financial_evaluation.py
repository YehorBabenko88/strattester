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
    kwargs=dict(train_events=[('BTC',t) for t in range(4)],test_events=[('BTC',4),('BTC',5)],seed=3)
    a=evaluate_controls(*args,**kwargs)
    assert a==evaluate_controls(*args,**kwargs)
    assert set(a)=={'zero','mean','persistence','linear','random_signal','label_shuffle','delayed_feature'}


def test_delayed_control_selects_strictly_prior_observation_of_same_series():
    from strattester.research.financial_evaluation import delayed_features
    history=[[1.],[100.],[2.],[200.],[3.],[300.]]
    events=[('BTC',10),('ETH',10),('BTC',20),('ETH',20),('BTC',30),('ETH',30)]
    assert delayed_features(history,events,[('BTC',20),('ETH',20),('BTC',30),('ETH',30)])==[[1.],[100.],[2.],[200.]]
    with pytest.raises(ValueError):delayed_features(history,events,[('BTC',10)])


def test_persistence_control_uses_the_targets_observed_return_channel():
    r=evaluate_controls([[.1],[.2]],[.1,.2],[[.3],[.4]],[.3,.4],
                        train_events=[('BTC',0),('BTC',1)],test_events=[('BTC',2),('BTC',3)])
    assert r['persistence']==0.


def test_funding_is_explicit_flat_charge_and_flat_positions_pay_nothing():
    report=evaluate_ledger([Trade('BTC',0,10,.1,1),Trade('ETH',0,10,.1,-1),
                            Trade('SOL',0,10,.1,0)],fee_bps=10,slippage_bps=5,funding_bps=20)
    assert report['returns']==pytest.approx([.095,-.105,0.])
    assert report['turnover']==4
    with pytest.raises(ValueError):
        evaluate_ledger([Trade('BTC',0,10,.1,1)],funding_bps=-1)


@pytest.mark.parametrize('mu,scale,target',[(1e308,1.,-1e308),(0.,1e-300,1.)])
def test_gaussian_score_rejects_finite_inputs_whose_score_overflows(mu,scale,target):
    with pytest.raises(ValueError,match='nonfinite distribution score'):
        gaussian_scores([mu],[scale],[target])
