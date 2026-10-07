from __future__ import annotations
from dataclasses import dataclass
from .shard_manifest import ShardState
from .storage_health import storage_health

@dataclass(frozen=True)
class MigrationBatchResult:
    attempted:int=0
    ready:int=0
    failed:int=0
    copied_rows:int=0

class ShardMigrator:
    def __init__(self,store):
        self.store=store
    def migrate_batch(self,symbols,limit=8,batch_size=20_000,min_free_bytes=2*1024**3):
        attempted=ready=failed=copied=0
        health=storage_health(self.store.root,min_free_bytes=min_free_bytes)
        if not health.ok:
            return MigrationBatchResult(0,0,0,0)
        cap=max(0,int(limit))
        for symbol in symbols:
            if attempted>=cap: break
            if self.store.manifest.ready(symbol):
                continue
            attempted+=1
            try:
                copied+=self.store.migrate_legacy_candles(symbol,batch_size=batch_size)
            except Exception as exc:
                record=self.store.manifest.get(symbol)
                rows=record.rows_copied if record else 0
                self.store.manifest.set(symbol,ShardState.FAILED,rows_copied=rows,error=str(exc))
                failed+=1
            else:
                ready+=1
        return MigrationBatchResult(attempted,ready,failed,copied)
