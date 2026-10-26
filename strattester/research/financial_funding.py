"""Bounded software-only funding contract, never producer authentication.

Rates are signed bps on fixed entry notional: positive means longs pay shorts.
Coverage is a caller assertion. It cannot unblock signed research sessions.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from .financial_contract import integer, digest


def _identity(value):
    if type(value) is not str or not 1 <= len(value) <= 256 or value.strip() != value:
        raise ValueError('invalid funding identity')


@dataclass(frozen=True)
class FundingEvent:
    instrument: str
    event_id: str
    settlement_ns: int
    available_ns: int
    rate: str
    rate_unit: str

    def rate_bps(self):
        if type(self.rate) is not str or not 1 <= len(self.rate) <= 64 or self.rate_unit != 'bps':
            raise ValueError('funding requires bounded decimal string in bps')
        try:
            value = Decimal(self.rate)
        except InvalidOperation as exc:
            raise ValueError('invalid funding rate') from exc
        # Research contract bound, not an exchange limit.
        if not value.is_finite() or value.copy_abs() > 10000:
            raise ValueError('funding rate outside research contract bound')
        return float(value)


@dataclass(frozen=True)
class FundingWindow:
    instrument: str
    start_ns: int
    end_ns: int
    as_of_ns: int
    source_sha256: str
    events: tuple[FundingEvent, ...]

    def validate(self):
        _identity(self.instrument)
        for value in (self.start_ns, self.end_ns, self.as_of_ns):integer(value, 'funding time')
        digest(self.source_sha256)
        if self.start_ns >= self.end_ns or self.end_ns > self.as_of_ns:
            raise ValueError('invalid funding coverage interval')
        if type(self.events) is not tuple or len(self.events) > 10000:
            raise ValueError('funding event budget')
        ids=set(); settlements=set()
        for event in self.events:
            if type(event) is not FundingEvent:raise ValueError('invalid funding event')
            _identity(event.instrument);_identity(event.event_id)
            integer(event.settlement_ns,'settlement');integer(event.available_ns,'availability')
            event.rate_bps()
            if (event.instrument != self.instrument or not self.start_ns <= event.settlement_ns <= self.end_ns
                or not event.settlement_ns <= event.available_ns <= self.as_of_ns
                or event.event_id in ids or event.settlement_ns in settlements):
                raise ValueError('funding identity/time/duplicate mismatch')
            ids.add(event.event_id);settlements.add(event.settlement_ns)
        return self


def funding_adjustments(trades, windows):
    """One complete caller-asserted window per exact instrument; (entry, exit]."""
    if type(windows) is not tuple or not 1 <= len(windows) <= 256:
        raise ValueError('BLOCKED: missing/bounded funding coverage required')
    if sum(len(w.events) for w in windows if type(w) is FundingWindow and type(w.events) is tuple)>10000:
        raise ValueError('aggregate funding event budget')
    by_instrument={}
    for window in windows:
        if type(window) is not FundingWindow:raise ValueError('invalid funding window')
        window.validate()
        if window.instrument in by_instrument:raise ValueError('duplicate funding window')
        by_instrument[window.instrument]=window
    if set(by_instrument) != {trade.instrument for trade in trades}:
        raise ValueError('BLOCKED: funding market coverage mismatch')
    output=[]
    for trade in trades:
        window=by_instrument[trade.instrument]
        if trade.start_ns < window.start_ns or trade.end_ns > window.end_ns:
            raise ValueError('BLOCKED: incomplete funding interval coverage')
        # Fixed unit entry notional, no mark-price/notional revaluation simulator.
        output.append(-trade.position*sum(e.rate_bps()/10000 for e in window.events
                      if trade.start_ns < e.settlement_ns <= trade.end_ns))
    return output
