"""Version-one offline financial boundary. All times are explicit integer ns.

An epoch is an externally trusted producer assertion, never inferred from times.
"""
from dataclasses import dataclass
import math
import re


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return value


def digest(value, length=64):
    if not isinstance(value,str) or re.fullmatch(f'[0-9a-f]{{{length}}}',value) is None:
        raise ValueError('invalid digest')
    return value


def finite(value, name):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric')
    return value


def timestamp_ns(value, unit):
    integer(value,'timestamp')
    factors={'ns':1,'us':1000,'ms':1_000_000,'s':1_000_000_000}
    if unit not in factors: raise ValueError('explicit timestamp unit required')
    return value*factors[unit]


@dataclass(frozen=True,order=True)
class Instrument:
    exchange: str
    market_type: str
    symbol: str

    def validate(self):
        if not all(isinstance(v,str) and v and v.strip()==v for v in
                   (self.exchange,self.market_type,self.symbol)):
            raise ValueError('invalid instrument identity')


@dataclass(frozen=True)
class Bar:
    instrument: Instrument
    timeframe_ns: int
    candle_open_ns: int
    candle_close_ns: int
    event_ns: int
    ingest_ns: int
    available_ns: int
    watermark_ns: int
    close: float
    quality: str
    eligible: bool
    complete: bool
    revision: int
    producer: str
    source_sha: str

    def validate(self,origin_ns):
        self.instrument.validate()
        integer(origin_ns,'origin')
        integer(self.timeframe_ns,'timeframe',1)
        for key in ('candle_open_ns','candle_close_ns','event_ns','ingest_ns','available_ns','watermark_ns'):
            integer(getattr(self,key),key)
        integer(self.revision,'revision',1)
        digest(self.source_sha,40)
        if not isinstance(self.producer,str) or not self.producer: raise ValueError('missing producer')
        if finite(self.close,'close')<=0: raise ValueError('close must be positive')
        if (self.candle_close_ns-self.candle_open_ns != self.timeframe_ns
            or self.candle_open_ns % self.timeframe_ns
            or not self.candle_open_ns<=self.event_ns<self.candle_close_ns
            or not self.candle_close_ns<=self.ingest_ns<=self.available_ns<=origin_ns
            or not self.candle_close_ns<=self.watermark_ns<=origin_ns):
            raise ValueError('noncausal or misaligned candle')
        if type(self.eligible) is not bool or type(self.complete) is not bool or not self.eligible or not self.complete or self.quality!='VERIFIED':
            raise ValueError('unverified candle')


@dataclass(frozen=True)
class Snapshot:
    bars: tuple[Bar,...]
    origin_ns: int
    coherence_id: str
    producers: tuple[str,...]

    def validate(self):
        integer(self.origin_ns,'origin')
        if type(self.bars) is not tuple or not self.bars or not isinstance(self.coherence_id,str) or not self.coherence_id:
            raise ValueError('BLOCKED: missing immutable snapshot/coherence')
        if type(self.producers) is not tuple or len(set(self.producers))!=len(self.producers):
            raise ValueError('duplicate producer')
        previous={}
        for bar in self.bars:
            bar.validate(self.origin_ns)
            key=(bar.instrument,bar.timeframe_ns)
            if key in previous and bar.candle_open_ns != previous[key]:
                raise ValueError('gap, duplicate, revision or unsorted bar')
            previous[key]=bar.candle_close_ns
        if set(self.producers)!={b.producer for b in self.bars}:
            raise ValueError('missing/extra producer provenance')
        return self


@dataclass(frozen=True)
class Prediction:
    instrument: Instrument
    origin_ns: int
    available_ns: int
    horizon_ns: int
    mu: float
    scale: float
    dataset_sha256: str
    model_sha256: str

    def validate(self):
        self.instrument.validate()
        integer(self.origin_ns,'origin'); integer(self.available_ns,'available'); integer(self.horizon_ns,'horizon',1)
        if self.available_ns<self.origin_ns or finite(self.scale,'scale')<=0:
            raise ValueError('invalid prediction availability/distribution')
        finite(self.mu,'mu'); digest(self.dataset_sha256); digest(self.model_sha256)
