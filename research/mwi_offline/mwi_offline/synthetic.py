"""Continuous artificial OHLCV; no market realism or performance claim."""
import math
import random

GENERATOR_VERSION="TOY_OSCILLATION_PLATEAU_V2"


def generate(seed=20261112, n=1800):
    if type(seed) is not int or type(n) is not int or not 60 <= n <= 10000:
        raise ValueError("SYNTHETIC_BOUNDS")
    rng=random.Random(seed)
    bars=[]
    price=100.0
    for i in range(n):
        regime=(i//300)%3
        amplitude=(2.4,3.0,1.9)[regime]
        wave=math.sin((i+1)*2*math.pi/(64 if regime==2 else 32))
        plateau=regime==2 and abs(wave)>.625
        shaped=max(-1.,min(1.,1.6*wave)) if regime==2 else wave
        target=100+amplitude*shaped+.25*math.sin(i*.009)
        close=target+rng.gauss(0,.005 if plateau else (.06,.13,.04)[regime])
        wick=(.01 if plateau else .10)+rng.random()*(.01 if plateau else .10)
        bars.append(dict(symbol="TOYUSDT",open_ms=i*60000,end_ms=(i+1)*60000,
                         available_ms=(i+1)*60000,open=price,high=max(price,close)+wick,
                         low=min(price,close)-wick,close=close,volume=100+20*regime+rng.random()*30))
        price=close
    return bars
