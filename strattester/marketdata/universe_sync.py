class UniverseSynchronizer:
    def __init__(self,registry,client):
        self.registry=registry
        self.client=client
    def sync(self,observed_at:int):
        symbols=self.client.fetch_linear_symbols()
        self.registry.reconcile(set(symbols),observed_at)
        return set(symbols)
