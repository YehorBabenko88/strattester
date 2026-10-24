from dataclasses import replace
from decimal import Decimal, localcontext
import math
import pytest
from strattester.research.financial_contract import Instrument, Bar, Snapshot, Prediction, timestamp_ns


def bar(t=0, symbol='BTCUSDT'):
    return Bar(Instrument('bybit','linear',symbol), 60, t, t+60, t+59, t+60, t+60,
               t+60, 100., 'VERIFIED', True, True, 1, 'producer', 'a'*40)


@pytest.mark.parametrize('value,unit', [(1.5,'ms'),(True,'ns'),('1','s'),(1,'auto'),(-1,'ns')])
def test_timestamp_boundary_rejects_implicit_conversions(value,unit):
    with pytest.raises(ValueError): timestamp_ns(value,unit)


def test_explicit_time_conversion():
    assert timestamp_ns(2,'ms') == 2_000_000
    assert timestamp_ns(2,'s') == 2_000_000_000


@pytest.mark.parametrize('change', [dict(close=float('nan')),dict(available_ns=121),
    dict(complete=False),dict(eligible=False),dict(quality='GOOD'),dict(revision=True),
    dict(candle_close_ns=61),dict(source_sha='invalid'),dict(ingest_ns=59)])
def test_invalid_observation_cannot_become_snapshot(change):
    with pytest.raises(ValueError): Snapshot((replace(bar(),**change),),120,'epoch',('producer',)).validate()


def test_gap_duplicate_and_missing_coherence_are_rejected():
    for rows,epoch in [((bar(),bar()),'epoch'),((bar(),bar(120)),'epoch'),((bar(),),'')]:
        with pytest.raises(ValueError): Snapshot(rows,240,epoch,('producer',)).validate()


def test_market_identity_does_not_alias_symbols():
    a = bar()
    b = replace(a,instrument=Instrument('bybit','spot','BTCUSDT'))
    Snapshot((a,b),60,'epoch',('producer',)).validate()


def test_prediction_has_explicit_horizon_and_distribution():
    p=Prediction(Instrument('bybit','linear','BTCUSDT'),60,60,120,.01,.2,'a'*64,'b'*64)
    p.validate()
    with pytest.raises(ValueError): replace(p,scale=0).validate()
    with pytest.raises(ValueError): replace(p,available_ns=59).validate()


def test_independent_decimal_log_return_oracle():
    from research.math_contract_reference import log_returns, sample_volatility
    with localcontext() as ctx:
        ctx.prec=50
        expected=float(Decimal('1.01').ln())
    assert log_returns([100.,101.])[0] == pytest.approx(expected,abs=1e-15)
    assert sample_volatility([1.,2.,3.]) == 1.
