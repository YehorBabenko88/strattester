from __future__ import annotations
import time
from strattester.engine.resource_manager import decide_resources

class BackgroundShardMigration:
    def __init__(self,migrator,symbol_provider,snapshot_provider,min_free_disk,
                 batch_symbols=2,interval_seconds=60):
        self.migrator=migrator
        self.symbol_provider=symbol_provider
        self.snapshot_provider=snapshot_provider
        self.min_free_disk=int(min_free_disk)
        self.batch_symbols=max(1,int(batch_symbols))
        self.interval_seconds=max(1,float(interval_seconds))
        self.next_run=0.0
    def maybe_run(self,now=None):
        now=time.time() if now is None else float(now)
        if now<self.next_run:return None
        snapshot=self.snapshot_provider()
        decision=decide_resources(snapshot,min_free_disk=self.min_free_disk)
        if decision.action!='normal':
            self.next_run=now+self.interval_seconds
            return None
        result=self.migrator.migrate_batch(
            self.symbol_provider(),limit=self.batch_symbols,
            min_free_bytes=self.min_free_disk)
        self.next_run=now+self.interval_seconds
        return result
