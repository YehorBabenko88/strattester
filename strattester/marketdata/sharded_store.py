from __future__ import annotations
from hashlib import sha256
from contextlib import contextmanager
import json
from pathlib import Path
import re
from .sqlite_store import SQLiteMarketStore,Candle
from .shard_manifest import ShardManifest,ShardState

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
    def __init__(self,root:Path,legacy_store=None,buckets:int=64,manifest=None):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.legacy_store=legacy_store
        self.buckets=max(1,int(buckets))
        self._stores={}
        self.manifest=manifest or ShardManifest.open(self.root/'manifest.sqlite3')

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
        if shard_path.exists() and self.manifest.ready(symbol):
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


    _DATASET_TABLES=(
        ('mark_prices',('symbol','timeframe','open_time','open','high','low','close','complete')),
        ('index_prices',('symbol','timeframe','open_time','open','high','low','close','complete')),
        ('premium_index',('symbol','timeframe','open_time','open','high','low','close','complete')),
        ('open_interest',('symbol','timeframe','open_time','value','complete')),
        ('funding',('symbol','funding_time','rate')),
        ('long_short_ratio',('symbol','timeframe','open_time','buy_ratio','sell_ratio','long_short_ratio')),
        ('public_trade_aggregates',('symbol','timeframe','open_time','buy_volume','sell_volume','turnover','trade_count','vwap','max_trade')),
    )

    def _copy_auxiliary_datasets(self,symbol,shard,batch_size):
        copied=0
        for table,columns in self._DATASET_TABLES:
            cols=','.join(columns)
            placeholders=','.join('?' for _ in columns)
            updates=','.join(f'{x}=excluded.{x}' for x in columns if x!='symbol')
            pk={'funding':'symbol,funding_time'}.get(table,'symbol,timeframe,open_time')
            cur=self.legacy_store.connection.execute(
                f"SELECT {cols} FROM {table} WHERE symbol=? ORDER BY rowid",(symbol,))
            while True:
                rows=cur.fetchmany(batch_size)
                if not rows: break
                with shard.connection:
                    shard.connection.executemany(
                        f"INSERT INTO {table}({cols}) VALUES({placeholders}) "
                        f"ON CONFLICT({pk}) DO UPDATE SET {updates}",rows)
                copied+=len(rows)
        return copied

    def _dataset_fingerprints(self,store,symbol,timeframe='1m'):
        result={}
        h=sha256(); count=0
        for candle in store.iter_candles(symbol,timeframe):
            h.update(json.dumps(candle.__dict__,sort_keys=True,separators=(',',':')).encode('utf-8'))
            h.update(b'\n'); count+=1
        result['candles']=(count,h.hexdigest())
        for table,columns in self._DATASET_TABLES:
            cols=','.join(columns)
            order='funding_time' if table=='funding' else 'timeframe,open_time'
            h=sha256(); count=0
            cur=store.connection.execute(
                f"SELECT {cols} FROM {table} WHERE symbol=? ORDER BY {order}",(symbol,))
            for row in cur:
                h.update(json.dumps(row,separators=(',',':'),ensure_ascii=False).encode('utf-8'))
                h.update(b'\n'); count+=1
            result[table]=(count,h.hexdigest())
        return result

    def migrate_legacy_candles(self,symbol:str,timeframe='1m',batch_size=20_000):
        if self.legacy_store is None:
            raise RuntimeError('legacy store is not configured')
        shard=self.for_symbol(symbol)
        source_cov=self.legacy_store.coverage(symbol,'candles',timeframe)
        initial_aux=self._dataset_fingerprints(self.legacy_store,symbol,timeframe)
        previous=self.manifest.get(symbol)
        self.manifest.set(symbol,ShardState.MIGRATING,rows_copied=previous.rows_copied if previous else 0)
        batch=[]; copied=0
        for row in self.legacy_store.iter_candles(symbol,timeframe,batch_size=batch_size):
            batch.append(row)
            if len(batch)>=batch_size:
                copied+=shard.upsert_candles(batch).accepted; batch.clear()
        if batch:
            copied+=shard.upsert_candles(batch).accepted
        # Re-read source coverage after copying. Live writes deliberately stay
        # in legacy while MIGRATING; if the source moved, do not promote this
        # pass. A later idempotent pass copies the tail and validates again.
        # Serialize final validation/promotion with routed writers across store
        # instances. Waiting writers choose their destination after this commit.
        with self._routing_transaction():
            copied+=self._copy_auxiliary_datasets(symbol,shard,batch_size)
            final_source_cov=self.legacy_store.coverage(symbol,'candles',timeframe)
            source_fingerprints=self._dataset_fingerprints(self.legacy_store,symbol,timeframe)
            target_fingerprints=self._dataset_fingerprints(shard,symbol,timeframe)
            target_cov=shard.coverage(symbol,'candles',timeframe)
            if final_source_cov!=source_cov or source_fingerprints!=initial_aux:
                self.manifest.set(symbol,ShardState.MIGRATING,rows_copied=target_cov.count,error='source changed during migration; retry required')
                raise RuntimeError('legacy source changed during migration; retry required')
            if (source_fingerprints!=target_fingerprints or target_cov.count!=final_source_cov.count or target_cov.earliest!=final_source_cov.earliest
                    or target_cov.latest!=final_source_cov.latest or target_cov.gaps!=final_source_cov.gaps
                    or not shard.integrity_check()):
                self.manifest.set(symbol,ShardState.FAILED,rows_copied=target_cov.count,error='shard migration validation failed')
                raise RuntimeError('shard migration validation failed')
            self.manifest.set(symbol,ShardState.SHARD_READY,rows_copied=target_cov.count)
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

    def _write_store(self,symbol):
        # Keep exactly one authoritative writer during migration.  Until the
        # manifest is promoted, live/repair writes stay in legacy so readers
        # cannot miss data that arrived while a historical copy was running.
        if self.manifest.ready(symbol) or self.legacy_store is None:
            return self.for_symbol(symbol)
        return self.legacy_store

    @contextmanager
    def _routing_transaction(self):
        self.manifest.con.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.manifest.con.commit()
        except Exception:
            self.manifest.con.rollback()
            raise

    def upsert_candles(self,records):
        records=list(records)
        if not records:
            from .sqlite_store import WriteStats
            return WriteStats()
        symbols={r.symbol for r in records}
        if len(symbols)!=1: raise ValueError('one routed write must contain exactly one symbol')
        symbol=next(iter(symbols))
        with self._routing_transaction():
            return self._write_store(symbol).upsert_candles(records)

    def upsert_price_klines(self,dataset,symbol,rows,timeframe='1m'):
        with self._routing_transaction():
            return self._write_store(symbol).upsert_price_klines(dataset,symbol,rows,timeframe)
    def upsert_open_interest(self,symbol,rows,timeframe='5m'):
        with self._routing_transaction():
            return self._write_store(symbol).upsert_open_interest(symbol,rows,timeframe)
    def upsert_funding(self,symbol,rows):
        with self._routing_transaction():
            return self._write_store(symbol).upsert_funding(symbol,rows)
    def upsert_long_short_ratio(self,symbol,rows,timeframe='5m'):
        with self._routing_transaction():
            return self._write_store(symbol).upsert_long_short_ratio(symbol,rows,timeframe)
    def upsert_public_trade_aggregates(self,symbol,rows,timeframe='1m'):
        with self._routing_transaction():
            return self._write_store(symbol).upsert_public_trade_aggregates(symbol,rows,timeframe)

    def integrity_check(self):
        return all(store.integrity_check() for store in self._stores.values())

    def close(self):
        errors=[]
        for store in tuple(self._stores.values()):
            try: store.close()
            except Exception as exc: errors.append(exc)
        self._stores.clear()
        try: self.manifest.close()
        except Exception as exc: errors.append(exc)
        if errors: raise errors[0]
