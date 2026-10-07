class UniverseSnapshotError(RuntimeError):
    pass

class UniverseSynchronizer:
    def __init__(self,registry,client,minimum_snapshot_ratio:float=0.5):
        self.registry=registry
        self.client=client
        self.minimum_snapshot_ratio=float(minimum_snapshot_ratio)

    def sync(self,observed_at:int):
        symbols=set(self.client.fetch_linear_symbols())
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
