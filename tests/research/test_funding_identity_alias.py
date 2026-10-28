"""Independent collision control for the posthoc funding helper boundary."""
import pytest
from strattester.research.financial_funding import FundingWindow, FundingEvent
from strattester.research.financial_walkforward_funding import score_control_funding


def test_control_funding_rejects_aliased_partition_identities():
    first = ('x|a', 'b', 'c', 1)
    second = ('x', 'a|b', 'c', 1)
    identity = '|'.join(map(str, first))
    assert first != second and identity == '|'.join(map(str, second))
    def window(rate):
        return FundingWindow(identity, 0, 100, 100, 'c'*64,
            (FundingEvent(identity, 'e', 5, 5, rate, 'bps'),)).validate()
    ledger = {'rows': [{'instrument': identity, 'start_ns': 0, 'end_ns': 10,
                       'gross_return': 0., 'position': 1}]}
    with pytest.raises(ValueError, match='funding identity collision'):
        score_control_funding(ledger, {first: window('10'), second: window('900')},
                              {'fee_bps': 0., 'slippage_bps': 0.})
