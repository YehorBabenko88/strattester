from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import re
from .sqlite_store import SQLiteMarketStore,Candle

_SAFE=re.compile(r'[^A-Za-z0-9_.-]+')

def safe_symbol(symbol:str)->str:
    value=_SAFE.sub('_',str(symbol).strip().upper()).strip('._')
    if not value:
        raise ValueError('empty symbol')
    return value

class ShardedMarketStore:
    """Routes each symbol to an independent SQLite database.

    Existing monolithic databases remain untouched and may be supplied as
    legacy_store for read fallback while new/repair writes go to shards.
    """
    def __init__(self,root:Path,legacy_store=None,buckets:int=64):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.legacy_store=legacy_store
        self.buckets=max(1,int(buckets))
        self._stores={}

    def shard_path(self,symbol:str)->Path:
        name=safe_symbol(symbol)
        digest=sha256(name.encode('utf-8')).hexdigest()
        bucket=int(digest[:8],16)%self.buckets
        return self.root/f'{bucket:02d}'/f'{name}.sqlite3'

    def for_symbol(self,symbol:str)->SQLiteMarketStore:
        key=safe_symbol(symbol)
        store=self._stores.get(key)
        if store is None:
            store=SQLiteMarketStore.open(self.shard_path(key))
            self._stores[key]=store
        return store

    def _read_store(self,symbol,dataset='candles',timeframe='1m',step_ms=60_000,start_ms=None,end_ms=None):
        shard_path=self.shard_path(symbol)
        if shard_path.exists():
            shard=self.for_symbol(symbol)
            cov=shard.coverage(symbol,dataset,timeframe,step_ms,start_ms,end_ms)
            if cov.count:
                return shard
        if self.legacy_store is not None:
            cov=self.legacy_store.coverage(symbol,dataset,timeframe,step_ms,start_ms,end_ms)
            if cov.count:
                return self.legacy_store
        return self.for_symbol(symbol)

    def coverage(self,symbol,dataset='candles',timeframe='1m',step_ms=60_000,start_ms=None,end_ms=None):
        # During migration a symbol must have a single authoritative source.
        # Never merge two independently mutable SQLite files implicitly.
        return self._read_store(symbol,dataset,timeframe,step_ms,start_ms,end_ms).coverage(
            symbol,dataset,timeframe,step_ms,start_ms,end_ms)

    def migrate_legacy_candles(self,symbol:str,timeframe='1m',batch_size=20_000):
        if self.legacy_store is None:
            raise RuntimeError('legacy store is not configured')
        shard=self.for_symbol(symbol)
        source_cov=self.legacy_store.coverage(symbol,'candles',timeframe)
        if source_cov.count==0:
            return 0
        batch=[]; copied=0
        for row in self.legacy_store.iter_candles(symbol,timeframe,batch_size=batch_size):
            batch.append(row)
            if len(batch)>=batch_size:
                copied+=shard.upsert_candles(batch).accepted; batch.clear()
        if batch:
            copied+=shard.upsert_candles(batch).accepted
        target_cov=shard.coverage(symbol,'candles',timeframe)
        if (target_cov.count!=source_cov.count or target_cov.earliest!=source_cov.earliest
                or target_cov.latest!=source_cov.latest or target_cov.gaps!=source_cov.gaps):
            raise RuntimeError('shard migration validation failed')
        return copied

    def promote_symbol(self,symbol:str):
        """Return the shard only after its data has been explicitly populated."""
        return self.for_symbol(symbol)

    def iter_candles(self,symbol,timeframe='1m',batch_size=20_000,start_ms=None,end_ms=None):
        store=self._read_store(symbol,'candles',timeframe,60_000,start_ms,end_ms)
        return store.iter_candles(symbol,timeframe,batch_size,start_ms,end_ms)

    def iter_public_trade_aggregates(self,symbol,timeframe='1m',start_ms=None,end_ms=None):
        store=self._read_store(symbol,'public_trade_aggregates',timeframe,60_000,start_ms,end_ms)
        return store.iter_public_trade_aggregates(symbol,timeframe,start_ms,end_ms)

    def upsert_candles(self,records):
        records=list(records)
        if not records:
            from .sqlite_store import WriteStats
            return WriteStats()
        symbols={r.symbol for r in records}
        if len(symbols)!=1: raise ValueError('one shard write must contain exactly one symbol')
        return self.for_symbol(next(iter(symbols))).upsert_candles(records)

    def upsert_price_klines(self,dataset,symbol,rows,timeframe='1m'):
        return self.for_symbol(symbol).upsert_price_klines(dataset,symbol,rows,timeframe)
    def upsert_open_interest(self,symbol,rows,timeframe='5m'):
        return self.for_symbol(symbol).upsert_open_interest(symbol,rows,timeframe)
    def upsert_funding(self,symbol,rows):
        return self.for_symbol(symbol).upsert_funding(symbol,rows)
    def upsert_long_short_ratio(self,symbol,rows,timeframe='5m'):
        return self.for_symbol(symbol).upsert_long_short_ratio(symbol,rows,timeframe)
    def upsert_public_trade_aggregates(self,symbol,rows,timeframe='1m'):
        return self.for_symbol(symbol).upsert_public_trade_aggregates(symbol,rows,timeframe)

    def integrity_check(self):
        return all(store.integrity_check() for store in self._stores.values())

    def close(self):
        errors=[]
        for store in tuple(self._stores.values()):
            try: store.close()
            except Exception as exc: errors.append(exc)
        self._stores.clear()
        if errors: raise errors[0]
