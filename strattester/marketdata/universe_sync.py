from __future__ import annotations
import math
import re

_SYMBOL = re.compile(r"[A-Z0-9]{1,36}USDT\Z")


class UniverseSnapshotError(RuntimeError):
    pass


class UniverseSynchronizer:
    def __init__(self,registry,client,minimum_snapshot_ratio:float=0.5):
        self.registry=registry
        self.client=client
        ratio=float(minimum_snapshot_ratio)
        if not math.isfinite(ratio) or not 0 < ratio <= 1:
            raise ValueError('minimum_snapshot_ratio must be finite and in (0,1]')
        self.minimum_snapshot_ratio=ratio

    def sync(self,observed_at:int):
        # A malformed source snapshot must not mutate the retained instrument
        # registry by treating individual characters or mapping keys as symbols.
        # Root-managed canonical Grid capability is still pending B/J acceptance.
        raw=self.client.fetch_linear_symbols()
        if type(raw) not in (set, frozenset, list, tuple):
            raise UniverseSnapshotError('instrument universe must be a finite symbol collection')
        if len(raw)>50_000:
            raise UniverseSnapshotError('instrument universe exceeds safety limit')
        if any(type(symbol) is not str or not _SYMBOL.fullmatch(symbol) for symbol in raw):
            raise UniverseSnapshotError('invalid symbol in instrument universe')
        symbols=set(raw)
        if len(symbols)!=len(raw):
            raise UniverseSnapshotError('instrument universe contains duplicate symbols')
        active=set(self.registry.active_symbols())
        if active:
            if not symbols:
                raise UniverseSnapshotError('exchange returned an empty instrument universe; refusing mass delist')
            ratio=len(symbols)/len(active)
            if ratio < self.minimum_snapshot_ratio:
                raise UniverseSnapshotError(
                    f'exchange instrument universe shrank suspiciously: {len(active)} -> {len(symbols)}; refusing mass delist')
        self.registry.reconcile(symbols,observed_at)
        return symbols
