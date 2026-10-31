"""Source-owned immutable historical run records. Digests establish integrity, not trust."""
from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
import math
import re
import time
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def row_quality(dataset, row):
    if dataset == 'public_trades':
        dataset = 'public_trade_aggregates'
    if dataset not in ('candles', 'mark_price', 'index_price', 'premium_index',
                       'open_interest', 'funding', 'long_short_ratio', 'public_trade_aggregates'):
        return False
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)
    if dataset in ('candles', 'mark_price', 'index_price', 'premium_index', 'open_interest'):
        if type(row.get('complete')) not in (bool, int) or row['complete'] != 1:
            return False
    if dataset in ('candles', 'mark_price', 'index_price', 'premium_index'):
        if not all(finite(row.get(k)) for k in ('open', 'high', 'low', 'close')):
            return False
        if not row['low'] <= row['open'] <= row['high'] or not row['low'] <= row['close'] <= row['high']:
            return False
    if dataset == 'candles':
        if min(row[k] for k in ('open', 'high', 'low', 'close')) <= 0:
            return False
        if not finite(row.get('volume')) or row['volume'] < 0:
            return False
        if row.get('turnover') is not None and (not finite(row['turnover']) or row['turnover'] < 0):
            return False
    fields = {'open_interest': ('value',), 'funding': ('rate',),
              'long_short_ratio': ('buy_ratio', 'sell_ratio', 'long_short_ratio'),
              'public_trade_aggregates': ('buy_volume', 'sell_volume', 'turnover', 'trade_count')}
    for key in fields.get(dataset, ()):
        if not finite(row.get(key)) or (dataset != 'funding' and row[key] < 0):
            return False
    return True


def validate(record):
    try:
        if not isinstance(record,dict) or not isinstance(record.get('producer_epoch'),str): return 'RECORD_INVALID'
        if type(record['api_version']['major']) is not int or type(record['api_version']['minor']) is not int or record['api_version'] != {'major':1,'minor':1}: return 'VERSION_UNSUPPORTED'
        if record['mode'] != 'HISTORICAL' or record['execution_authority'] is not False: return 'MODE_INVALID'
        if record['completion_receipt'] != digest({k:v for k,v in record.items() if k != 'completion_receipt'}): return 'RECEIPT_INVALID'
        if record['producer']!='strattester': return 'IDENTITY_INVALID'
        uuid.UUID(record['producer_epoch'])
        d=record['dataset']
        if d['coverage'] != 'COMPLETE' or d['missing_data'] != []: return 'GAP'
        if not re.fullmatch('[0-9a-f]{64}',d['fingerprint']): return 'DATASET_INVALID'
        if d['fingerprint']!=digest(dict(dataset={k:v for k,v in d.items() if k!='fingerprint'},rows=record['input_snapshot'])): return 'DATASET_DIGEST_INVALID'
        if not isinstance(record['input_snapshot'],list) or not record['input_snapshot']: return 'DATASET_INVALID'
        for key in ('start_ms','end_ms'):
            if type(d[key]) is not int or d[key]<0: return 'BOUNDS_INVALID'
        if d['start_ms']>d['end_ms']: return 'BOUNDS_INVALID'
        from strattester.engine.executor import _step_ms
        descriptors=[]
        for entry in record['input_snapshot']:
            if not isinstance(entry,dict) or not re.fullmatch('[1-9][0-9]*[mhd]',entry['timeframe']): return 'DATASET_INVALID'
            step=_step_ms(entry['timeframe'])
            if d['start_ms']%step or d['end_ms']%step: return 'BOUNDS_INVALID'
            rows=entry['rows']
            if len(rows)!=(d['end_ms']-d['start_ms'])//step+1: return 'GAP'
            for i,row in enumerate(rows):
                timestamp=row.get('open_time',row.get('ts',row.get('funding_time')))
                if type(timestamp) is not int or timestamp!=d['start_ms']+i*step: return 'GAP'
                if row.get('symbol',d['symbol'])!=d['symbol'] or row.get('timeframe',entry['timeframe'])!=entry['timeframe']: return 'DATASET_INVALID'
                if not row_quality(entry['dataset'],row): return 'DATA_QUALITY_INVALID'
            descriptors.append(dict(dataset=entry['dataset'],timeframe=entry['timeframe'],count=len(rows)))
        if descriptors!=d['datasets'] or len({(x['dataset'],x['timeframe']) for x in descriptors})!=len(descriptors): return 'DATASET_INVALID'
        if d['timeframe']!=','.join(sorted({x['timeframe'] for x in descriptors})): return 'DATASET_INVALID' 
        if d['market_type'] not in ('spot','linear','inverse'): return 'MARKET_TYPE_INVALID'
        for key in ('source_identity','symbol','timeframe'):
            if not isinstance(d[key],str) or not d[key]: return 'IDENTITY_MISSING'
        for key in ('producer_identity','producer_epoch','source_revision','model','execution_assumptions'):
            if not record[key]: return 'IDENTITY_MISSING'
        if not re.fullmatch('[0-9a-f]{40}',record['source_revision']): return 'REVISION_INVALID'
        s=record['strategy']
        if not s['id'] or not s['version'] or not re.fullmatch('[0-9a-f]{64}',s['fingerprint']) or not isinstance(s['parameters'],dict): return 'STRATEGY_INVALID'
        if type(record['completed_at_ms']) is not int or record['completed_at_ms']<0: return 'COMPLETION_INVALID'
        if record['completed_at_ms']<d['end_ms']: return 'COMPLETION_INVALID'
        if not isinstance(record['model'],dict) or not isinstance(record['execution_assumptions'],dict): return 'ASSUMPTIONS_INVALID'
        if not isinstance(record['metrics'],(dict,list,tuple)): return 'METRICS_INVALID'
        model=record['model']; assumptions=record['execution_assumptions']
        if not isinstance(model.get('kind'),str) or not model['kind'] or not isinstance(model.get('version'),str) or not model['version']: return 'MODEL_VERSION_MISSING'
        if not isinstance(assumptions.get('execution'),str) or not assumptions['execution']: return 'ASSUMPTIONS_INVALID'
        for key in ('fees','slippage'):
            if type(assumptions.get(key)) not in (int,float) or assumptions[key]<0: return 'ASSUMPTIONS_INVALID' 
        uuid.UUID(record['run_id']); canonical(record['metrics'])
        return None
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,RecursionError): return 'RECORD_INVALID'


class FrozenDatasets:
    research_snapshot_active = True
    """Read interface over detached immutable input records, never a mutable source."""
    def __init__(self,symbol,entries): self.symbol=symbol; self.entries=entries
    def _entry(self,symbol,dataset,timeframe):
        if symbol!=self.symbol: raise ValueError('snapshot symbol mismatch')
        return self.entries[(dataset,timeframe)]
    def iter_candles(self,symbol,timeframe,start_ms=None,end_ms=None):
        return iter(self._entry(symbol,'candles',timeframe)['objects'])
    def iter_public_trade_aggregates(self,symbol,timeframe,start_ms=None,end_ms=None):
        entry=self.entries.get(('public_trade_aggregates',timeframe)) or self.entries.get(('public_trades',timeframe))
        if symbol!=self.symbol or entry is None: raise ValueError('snapshot mismatch')
        return iter(dict(x) for x in entry['objects'])
    def coverage(self,symbol,dataset,timeframe='1m',**kwargs):
        from types import SimpleNamespace
        times=self._entry(symbol,dataset,timeframe)['times']
        return SimpleNamespace(count=len(times),gaps=(),earliest=times[0],latest=times[-1])

    def validate_range(self, symbol, dataset, timeframe, start_ms, end_ms, step_ms):
        entry = self._entry(symbol, dataset, timeframe)
        rows = entry['rows']
        selected = [row for row in rows if start_ms <= row.get('open_time', row.get('ts', row.get('funding_time'))) <= end_ms]
        times = [row.get('open_time', row.get('ts', row.get('funding_time'))) for row in selected]
        return (times == list(range(start_ms, end_ms + 1, step_ms))
                and all(row_quality(dataset, row) for row in selected))


def snapshot_inputs(definition,store,symbol,start_ms,end_ms):
    """Snapshot every declared dataset. SQLite backup pins a consistent image per
    source file before extracting exact inclusive windows. Shard routing is
    resolved once per requirement; no mutable source is consulted by execution.
    """
    import sqlite3
    from strattester.marketdata.sqlite_store import SQLiteMarketStore
    from strattester.engine.executor import _step_ms
    mapping={'candles':('candles','open_time'), 'mark_price':('mark_prices','open_time'),
             'index_price':('index_prices','open_time'),'premium_index':('premium_index','open_time'),
             'open_interest':('open_interest','open_time'),'funding':('funding','funding_time'),
             'long_short_ratio':('long_short_ratio','open_time'),
             'public_trades':('public_trade_aggregates','open_time'),
             'public_trade_aggregates':('public_trade_aggregates','open_time')}
    entries={}; images={}
    try:
        for req in definition.requirements:
            dataset=getattr(req.dataset,'value',req.dataset)
            if dataset not in mapping: raise ValueError('DATASET_ADAPTER_UNAVAILABLE')
            for tf in req.timeframes or ('1m',):
                if not re.fullmatch('[1-9][0-9]*[mhd]',tf): raise ValueError('TIMEFRAME_INVALID')
                step=_step_ms(tf)
                if start_ms%step or end_ms%step: raise ValueError('BOUNDS_UNALIGNED')
                source=store._read_store(symbol,dataset,tf,step,start_ms,end_ms) if hasattr(store,'_read_store') else store
                connection=getattr(source,'connection',None)
                if connection is None:
                    if dataset!='candles': raise ValueError('DATASET_ADAPTER_UNAVAILABLE')
                    objects=tuple(source.iter_candles(symbol,tf,start_ms=start_ms,end_ms=end_ms))
                    rows=[asdict(x) for x in objects]
                    times=[x.open_time for x in objects]
                else:
                    if id(connection) not in images:
                        image=sqlite3.connect(':memory:')
                        connection.backup(image)
                        image.execute('PRAGMA query_only=ON')
                        images[id(connection)]=SQLiteMarketStore(':memory:',image)
                    frozen=images[id(connection)]; table,col=mapping[dataset]
                    if dataset=='candles' and frozen._legacy_candles: col='ts'
                    columns=[r[1] for r in frozen.connection.execute('PRAGMA table_info('+table+')')]
                    clauses=['symbol=?',col+'>=?',col+'<=?']; args=[symbol,start_ms,end_ms]
                    if 'timeframe' in columns: clauses.append('timeframe=?'); args.append(tf)
                    rows=[dict(zip(columns,row)) for row in frozen.connection.execute('SELECT * FROM '+table+' WHERE '+' AND '.join(clauses)+' ORDER BY '+col,args)]
                    times=[x[col] for x in rows]
                    if dataset=='candles': objects=tuple(frozen.iter_candles(symbol,tf,start_ms=start_ms,end_ms=end_ms))
                    elif dataset in ('public_trades','public_trade_aggregates'): objects=tuple(frozen.iter_public_trade_aggregates(symbol,tf,start_ms=start_ms,end_ms=end_ms))
                    else: objects=()
                expected=(end_ms-start_ms)//step+1
                if len(times)!=expected or any(type(t) is not int or t!=start_ms+i*step for i,t in enumerate(times)) or any(not row_quality(dataset,x) for x in rows): raise ValueError('GAP')
                if dataset=='candles' and any(x.symbol!=symbol or x.timeframe!=tf for x in objects): raise ValueError('DATASET_IDENTITY_MISMATCH')
                canonical(rows)
                entries[(dataset,tf)]={'objects':objects,'rows':rows,'times':times}
        if not entries: raise ValueError('DATASET_MISSING')
        return FrozenDatasets(symbol,entries),[dict(dataset=k[0],timeframe=k[1],rows=v['rows']) for k,v in sorted(entries.items())]
    finally:
        for image in images.values(): image.connection.close()


def execute_owned(definition, store, symbol, start_ms, end_ms, result_store, *, source_identity,
                  market_type, producer_identity, source_revision, model, execution_assumptions,
                  parameters=None, checkpoint=None, lease_validator=lambda: True, cancelled=lambda: False,
                  research_permission=None, closed_before_ms=None):
    """Freeze the exact strategy input before execution; publish once after successful return.

    All declared supported datasets are frozen before execution. Unknown datasets
    fail closed until an exact snapshot adapter is implemented.
    """
    from strattester.engine.executor import execute_strategy, require_execution_permission
    require_execution_permission(definition, research_permission)
    if checkpoint is not None: raise ValueError('CHECKPOINT_BINDING_UNAVAILABLE')
    if parameters: raise ValueError('PARAMETERS_ADAPTER_UNAVAILABLE')
    if type(start_ms) is not int or type(end_ms) is not int or start_ms<0 or end_ms<start_ms: raise ValueError('BOUNDS_INVALID')
    if any(req.lookback_ms is not None for req in definition.requirements):
        raise ValueError('LOOKBACK_BINDING_UNAVAILABLE')
    factory = getattr(store, 'research_snapshot', None)
    if factory is None:
        raise RuntimeError('coherent research snapshot unavailable')
    with factory(symbol, definition.requirements) as snapshot:
        frozen,payload=snapshot_inputs(definition,snapshot,symbol,start_ms,end_ms)
    timeframes=sorted({x['timeframe'] for x in payload})
    dataset=dict(source_identity=source_identity,market_type=market_type,symbol=symbol,timeframe=','.join(timeframes),start_ms=start_ms,end_ms=end_ms,coverage='COMPLETE',missing_data=[],datasets=[dict(dataset=x['dataset'],timeframe=x['timeframe'],count=len(x['rows'])) for x in payload])
    dataset['fingerprint']=digest(dict(dataset=dataset,rows=payload))
    run_id=str(uuid.uuid4())
    result_store.begin_owned(run_id)
    try:
        if cancelled(): raise RuntimeError('CANCELLED')
        result=execute_strategy(definition,frozen,symbol,checkpoint=checkpoint,start_ms=start_ms,end_ms=end_ms,
                                research_permission=research_permission,cancel=cancelled,closed_before_ms=closed_before_ms)
        if cancelled() or not lease_validator(): raise RuntimeError('PUBLICATION_FENCED')
        output=asdict(result.output) if is_dataclass(result.output) else result.output
        record=dict(api_version=dict(major=1,minor=1),producer='strattester',producer_identity=producer_identity,
                    source_revision=source_revision,producer_epoch=result_store.producer_epoch,run_id=run_id,mode='HISTORICAL',execution_authority=False,
                    input_snapshot=payload,dataset=dataset,strategy=dict(id=result.strategy_id,version=result.strategy_version,fingerprint=result.fingerprint,parameters=parameters or {}),
                    model=model,execution_assumptions=execution_assumptions,completed_at_ms=time.time_ns()//1000000,metrics=output)
        record['completion_receipt']=digest(record)
        reason=validate(record)
        if reason: raise ValueError(reason)
        result_store.complete_owned(run_id,record,lease_validator)
        return result
    except BaseException:
        result_store.abort_owned(run_id)
        raise
