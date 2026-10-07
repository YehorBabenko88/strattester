"""Multi-timescale memory for the scientific organism."""
from __future__ import annotations
from collections import defaultdict,deque
from dataclasses import dataclass
from math import exp

@dataclass(frozen=True)
class MemoryState:
    short_signal:float
    regime_signal:float
    long_signal:float
    short_samples:int
    regime_samples:int
    long_samples:int

class MultiTimescaleMemory:
    def __init__(self,*,short_window=8,regime_window=32,long_window=128,
                 short_decay=.65,regime_decay=.90,long_decay=.985):
        if not 0<=short_decay<1 or not 0<=regime_decay<1 or not 0<=long_decay<1:
            raise ValueError("decays must be in [0,1)")
        self.windows=(int(short_window),int(regime_window),int(long_window))
        self.decays=(float(short_decay),float(regime_decay),float(long_decay))
        self._short=defaultdict(lambda:deque(maxlen=self.windows[0]))
        self._regime=defaultdict(lambda:deque(maxlen=self.windows[1]))
        self._long=defaultdict(lambda:deque(maxlen=self.windows[2]))

    @staticmethod
    def _ewma(xs,decay):
        if not xs:return 0.0
        v=float(xs[0])
        for x in list(xs)[1:]:v=decay*v+(1-decay)*float(x)
        return v

    def add(self,channel_id:str,score:float,regime:str):
        self._short[channel_id].append(float(score))
        self._regime[(channel_id,regime)].append(float(score))
        self._long[channel_id].append(float(score))

    def state(self,channel_id:str,regime:str):
        s=self._short[channel_id];r=self._regime[(channel_id,regime)];l=self._long[channel_id]
        return MemoryState(self._ewma(s,self.decays[0]),self._ewma(r,self.decays[1]),
                           self._ewma(l,self.decays[2]),len(s),len(r),len(l))

    def reactive_modifier(self,channel_id:str,regime:str,cap=.20):
        """Short/regime memory may modulate current sensitivity, never consolidate it."""
        x=self.state(channel_id,regime)
        raw=.6*x.short_signal+.4*x.regime_signal
        return max(-cap,min(cap,raw))

    def consolidation_candidate(self,channel_id:str,regime:str,min_long_samples=16,
                                agreement_tolerance=.35):
        x=self.state(channel_id,regime)
        if x.long_samples<min_long_samples:return None
        # Long-term learning is blocked when regime and lifetime memories disagree strongly.
        if abs(x.regime_signal-x.long_signal)>agreement_tolerance:return None
        return x.long_signal
