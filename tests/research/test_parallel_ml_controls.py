import pytest
from strattester.research.financial_evaluation import evaluate_controls


@pytest.mark.parametrize('train_events', [
    [('BTC', 0), ('BTC', 2)],  # exact test origin is unavailable to training
    [('BTC', 0), ('BTC', 3)],  # future same-series row
    [('ETH', 0), ('ETH', 3)],  # global training cutoff applies across series
])
def test_controls_reject_training_at_or_after_first_test_before_fit(train_events, monkeypatch):
    from research.alphafold_training.baselines import MeanReturnBaseline
    def forbidden_fit(*args, **kwargs):
        pytest.fail('chronological admission must precede any baseline fitting')
    monkeypatch.setattr(MeanReturnBaseline, 'fit', forbidden_fit)
    with pytest.raises(ValueError, match='training.*strictly before.*test'):
        evaluate_controls([[.1], [.2]], [.1, .2], [[.3], [.4]], [.3, .4],
                          train_events=train_events,
                          test_events=[('BTC', 2), ('BTC', 4)],
                          history_x=[[.1], [.3], [.4]],
                          history_events=[('BTC', 0), ('BTC', 2), ('BTC', 4)])


def test_controls_admit_unsorted_past_training_and_multiseries_oos():
    report = evaluate_controls([[.2], [.1]], [.2, .1], [[.3], [.4]], [.3, .4],
        train_events=[('ETH', 1), ('BTC', 0)],
        test_events=[('BTC', 2), ('ETH', 3)], seed=12)
    assert report['persistence'] == 0.
    assert set(report) == {'zero', 'mean', 'persistence', 'linear',
                           'random_signal', 'label_shuffle', 'delayed_feature'}

