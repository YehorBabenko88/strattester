"""Synthetic contract examples only; independent Decimal cash arithmetic."""
from dataclasses import replace
from decimal import Decimal
import pytest
from strattester.research.financial_evaluation import Trade, evaluate_ledger
from strattester.research.financial_funding import FundingEvent, FundingWindow


def window(events=None, **kwargs):
    event = FundingEvent('venue/perpetual/BTC', 'settlement-1', 10, 11, '25', 'bps')
    return FundingWindow('venue/perpetual/BTC', 0, 20, 20, 'a'*64,
                         (event,) if events is None else events, **kwargs)


@pytest.mark.parametrize('position,rate', [(1,'25'),(-1,'25'),(0,'25'),(1,'-25'),(-1,'-25')])
def test_signed_funding_matches_decimal_cash_oracle(position, rate):
    event = replace(window().events[0], rate=rate)
    trade = Trade('venue/perpetual/BTC', 0, 20, .125, position)
    report = evaluate_ledger([trade], fee_bps=3, slippage_bps=2,
                             funding_windows=(window((event,)),))
    expected = (Decimal(position)*Decimal('.125') - Decimal(2*abs(position))*Decimal(5)/10000
                - Decimal(position)*Decimal(rate)/10000)
    assert report['returns'] == pytest.approx([float(expected)], abs=1e-15)
    assert report['funding_status'] == 'RESEARCH_CONTRACT_ONLY_NOT_PRODUCER_AUTHENTICATED'


def test_settlement_is_start_exclusive_end_inclusive_and_no_double_charge():
    events = tuple(replace(window().events[0], event_id=str(t), settlement_ns=t,
                           available_ns=t) for t in (0,10,20))
    trades = [Trade('venue/perpetual/BTC', 0, 10, 0., 1),
              Trade('venue/perpetual/BTC', 10, 20, 0., -1)]
    assert evaluate_ledger(trades, funding_windows=(window(events),))['returns'] == [-.0025,.0025]


@pytest.mark.parametrize('change', [dict(rate_unit='fraction'),dict(rate='NaN'),
    dict(rate='1e999'),dict(rate='1e999999999'),dict(rate=True),dict(settlement_ns=21),dict(available_ns=21),
    dict(available_ns=9),dict(instrument='other/perpetual/BTC'),dict(event_id='')])
def test_invalid_units_times_rate_and_identity_are_rejected(change):
    with pytest.raises(ValueError):
        evaluate_ledger([Trade('venue/perpetual/BTC',0,20,0.,1)],
            funding_windows=(window((replace(window().events[0], **change),)),))


@pytest.mark.parametrize('events', [lambda e:(e,e),
    lambda e:(e,replace(e,event_id='different')),lambda e:(e,replace(e,settlement_ns=12))])
def test_duplicate_event_or_settlement_identity_is_rejected(events):
    with pytest.raises(ValueError): window(events(window().events[0])).validate()


def test_missing_coverage_double_charge_and_unused_window_rejected():
    trade = Trade('venue/perpetual/BTC',0,20,0.,1)
    for windows in ((), (replace(window(),end_ns=19),), (replace(window(),instrument='other'),)):
        with pytest.raises(ValueError): evaluate_ledger([trade],funding_windows=windows)
    with pytest.raises(ValueError):evaluate_ledger([trade],funding_bps=1,funding_windows=(window(),))


def test_explicit_empty_window_is_contract_assertion_not_real_funding_proof():
    report=evaluate_ledger([Trade('venue/perpetual/BTC',0,20,0.,1)],funding_windows=(window(()),))
    assert report['returns']==[0.]
    assert report['funding_status']=='RESEARCH_CONTRACT_ONLY_NOT_PRODUCER_AUTHENTICATED'


def test_no_exposure_during_gap_and_instrument_order_is_preserved():
    # Only settlement 10 has exposure; 0 is entry-excluded and 20 falls in a gap.
    events=tuple(replace(window().events[0],event_id=str(t),settlement_ns=t,
                         available_ns=t) for t in (0,10,20))
    trades=[Trade('venue/perpetual/BTC',25,30,0.,-1),
            Trade('venue/perpetual/BTC',0,10,0.,1)]
    coverage=replace(window(events),end_ns=30,as_of_ns=30)
    assert evaluate_ledger(trades,funding_windows=(coverage,))['returns']==[-.0025,0.]


def test_bounded_contract_rejects_duplicate_windows_and_future_coverage():
    trade=Trade('venue/perpetual/BTC',0,20,0.,1)
    with pytest.raises(ValueError):evaluate_ledger([trade],funding_windows=(window(),window()))
    with pytest.raises(ValueError):replace(window(),as_of_ns=19).validate()
    with pytest.raises(ValueError):replace(window(),source_sha256='not evidence').validate()


def test_funding_admission_bounds_total_events_across_instruments():
    from strattester.research.financial_funding import FundingEvent, FundingWindow
    windows=tuple(FundingWindow(instrument,0,6000,6000,'a'*64,
        tuple(FundingEvent(instrument,str(t),t,t,'0','bps') for t in range(1,5002)))
        for instrument in ('venue/linear/A','venue/linear/B'))
    trades=[Trade(w.instrument,0,6000,0.,1) for w in windows]
    with pytest.raises(ValueError,match='aggregate funding event budget'):
        evaluate_ledger(trades,funding_windows=windows)


def test_funding_cancelling_settlements_match_decimal_under_permutation():
    from itertools import permutations
    events=tuple(replace(window().events[0],event_id=str(i),settlement_ns=i,available_ns=i,rate=rate)
                 for i,rate in enumerate(('10000','0.000000000001','-10000'),1))
    expected=-sum((Decimal(e.rate)/Decimal(10000) for e in events),Decimal(0))
    trade=Trade(window().instrument,0,20,0.,1)
    for ordered in permutations(events):
        report=evaluate_ledger([trade],funding_windows=(window(ordered),))
        assert report['returns'][0]==pytest.approx(float(expected),rel=1e-14,abs=1e-30)
