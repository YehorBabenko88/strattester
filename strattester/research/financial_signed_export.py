"""Signed immutable export consumer, never a native Grid exporter.

Authenticates an independently provisioned producer; signed source assertions
are not proof that a latest-state production DB retained historical truth.
"""
from dataclasses import dataclass,asdict,fields
from hashlib import sha256
from pathlib import Path
from .financial_contract import Instrument,Bar,Snapshot,integer,digest
from .financial_snapshot import canonical_bytes,bounded_json,verified_bytes,load_snapshot
from .financial_signatures import OpenSSLVerifier,load_trust_store,decode64

SIGNATURE_DOMAIN=b'STRATTESTER_GRID_EXPORT_V1\x00'
SNAPSHOT_SCHEMA_SHA256=sha256(canonical_bytes({'version':1,'Instrument':[f.name for f in fields(Instrument)],'Bar':[f.name for f in fields(Bar)],'Snapshot':[f.name for f in fields(Snapshot)]})).hexdigest()


def identity(value):
    if type(value) is not str or not 1<=len(value)<=256:raise ValueError('invalid export identity')
    return value


@dataclass(frozen=True,order=True)
class SourceIdentity:
    source_id: str
    engine: str
    schema_sha256: str

    def validate(self):
        identity(self.source_id);digest(self.schema_sha256)
        if self.engine not in ('fixture','sqlite','postgresql','sharded_sqlite'):raise ValueError('unknown source engine')
        return self


@dataclass(frozen=True,order=True)
class MarketPartition:
    exchange: str
    market_type: str
    symbol: str
    timeframe_ns: int

    def validate(self):
        Instrument(self.exchange,self.market_type,self.symbol).validate();integer(self.timeframe_ns,'partition timeframe',1)
        return self


@dataclass(frozen=True)
class ExportPolicy:
    producer_id: str
    coherence_epoch_id: str
    knowledge_cutoff_ns: int
    sources: tuple[SourceIdentity,...]
    partitions: tuple[MarketPartition,...]
    verification_ns: int
    scope: str = 'SYNTHETIC_ENGINEERING_ONLY'

    def validate(self):
        identity(self.producer_id);identity(self.coherence_epoch_id);integer(self.knowledge_cutoff_ns,'knowledge cutoff',1)
        integer(self.verification_ns,'trusted verification time',1)
        if self.verification_ns<self.knowledge_cutoff_ns:raise ValueError('verification before knowledge cutoff')
        if (type(self.sources) is not tuple or not 1<=len(self.sources)<=64 or len({s.source_id for s in self.sources})!=len(self.sources)
            or type(self.partitions) is not tuple or not 1<=len(self.partitions)<=256 or len(set(self.partitions))!=len(self.partitions)):
            raise ValueError('source/partition membership budget')
        if self.scope not in ('SYNTHETIC_ENGINEERING_ONLY','PRODUCER_ATTESTED_RESEARCH') or (self.scope=='PRODUCER_ATTESTED_RESEARCH' and any(s.engine=='fixture' for s in self.sources)):raise ValueError('invalid source scope policy')
        for source in self.sources:source.validate()
        for partition in self.partitions:partition.validate()
        return self


@dataclass(frozen=True)
class AttestedExport:
    snapshot: Snapshot
    provenance: dict


def load_attested_export(*,manifest_path,manifest_sha256,snapshot_path,trust_store_path,trust_store_sha256,
                         policy,verifier,max_snapshot_bytes=8*1024*1024,cancel=lambda:False):
    from .financial_training import TrainingCancelled
    def check():
        if cancel():raise TrainingCancelled('cancelled signed export verification')
    check();policy.validate();integer(max_snapshot_bytes,'snapshot byte budget',1)
    if max_snapshot_bytes>8*1024*1024:raise ValueError('snapshot byte budget exceeds hard limit')
    if type(verifier) is not OpenSSLVerifier:raise ValueError('independent pinned verifier required; no callback')
    data=verified_bytes(manifest_path,manifest_sha256,256*1024);m=bounded_json(data)
    required={'version','producer_id','producer_build_sha','key_id','export_id','coherence_epoch_id','snapshot_schema_version',
              'snapshot_schema_sha256','snapshot_sha256','snapshot_bytes','row_count','knowledge_cutoff_ns','issued_at_ns','scope','partitions','sources','signature_b64'}
    if (set(m)!=required or type(m['version']) is not int or m['version']!=1
        or type(m['snapshot_schema_version']) is not int or m['snapshot_schema_version']!=1
        or m['snapshot_schema_sha256']!=SNAPSHOT_SCHEMA_SHA256):raise ValueError('unsupported export schema/version')
    for name in ('producer_id','key_id','export_id','coherence_epoch_id'):identity(m[name])
    digest(m['producer_build_sha'],40);digest(m['snapshot_sha256'])
    for name in ('snapshot_bytes','row_count','knowledge_cutoff_ns','issued_at_ns'):integer(m[name],name,1)
    if m['snapshot_bytes']>max_snapshot_bytes or m['row_count']>100_000:raise ValueError('export allocation budget')
    if (m['producer_id']!=policy.producer_id or m['coherence_epoch_id']!=policy.coherence_epoch_id
        or m['knowledge_cutoff_ns']!=policy.knowledge_cutoff_ns):raise ValueError('producer/epoch/cutoff policy mismatch')
    if not policy.knowledge_cutoff_ns<=m['issued_at_ns']<=policy.verification_ns:raise ValueError('invalid export issue time')
    if policy.verification_ns-m['issued_at_ns']>900_000_000_000:raise ValueError('stale export issue time')
    if m['scope']!=policy.scope:raise ValueError('export scope policy mismatch')
    trust=load_trust_store(trust_store_path,trust_store_sha256);check()
    key=trust.key(m['producer_id'],m['key_id'],m['issued_at_ns'])
    trust.key(m['producer_id'],m['key_id'],policy.verification_ns)
    unsigned={k:v for k,v in m.items() if k!='signature_b64'}
    verifier.verify(key,SIGNATURE_DOMAIN+canonical_bytes(unsigned),decode64(m['signature_b64'],64));check()
    if type(m['sources']) is not list or len(m['sources'])!=len(policy.sources):raise ValueError('source membership')
    expected={s.source_id:s for s in policy.sources};seen=set()
    for row in m['sources']:
        if type(row) is not dict or set(row)!={'source_id','engine','schema_sha256','snapshot_id','coherence_epoch_id','complete','first_availability_retained','revision_history_retained','event_watermark_ns','availability_watermark_ns'}:
            raise ValueError('source receipt schema')
        source=expected.get(row['source_id'])
        if (source is None or row['source_id'] in seen or row['engine']!=source.engine or row['schema_sha256']!=source.schema_sha256
            or row['coherence_epoch_id']!=policy.coherence_epoch_id):raise ValueError('source/schema/epoch identity')
        seen.add(row['source_id']);identity(row['snapshot_id'])
        if any(row[k] is not True for k in ('complete','first_availability_retained','revision_history_retained')):
            raise ValueError('missing historical availability/revision/coherence facts')
        for name in ('event_watermark_ns','availability_watermark_ns'):
            integer(row[name],name)
            if row[name]<policy.knowledge_cutoff_ns:raise ValueError('incomplete source cut')
    if type(m['partitions']) is not list or len(m['partitions'])!=len(policy.partitions):raise ValueError('partition membership')
    try:partitions=tuple(MarketPartition(**p).validate() for p in m['partitions'])
    except TypeError as exc:raise ValueError('partition schema') from exc
    if len(set(partitions))!=len(partitions) or set(partitions)!=set(policy.partitions):raise ValueError('market identity mismatch')
    check()
    snapshot_data=verified_bytes(snapshot_path,m['snapshot_sha256'],max_snapshot_bytes)
    if len(snapshot_data)!=m['snapshot_bytes']:raise ValueError('signed snapshot byte count mismatch')
    snapshot=load_snapshot(snapshot_path,m['snapshot_sha256'],trusted_producers={policy.producer_id},expected_coherence=policy.coherence_epoch_id,max_bytes=max_snapshot_bytes)
    actual={MarketPartition(b.instrument.exchange,b.instrument.market_type,b.instrument.symbol,b.timeframe_ns) for b in snapshot.bars}
    if (snapshot.origin_ns!=policy.knowledge_cutoff_ns or len(snapshot.bars)!=m['row_count']
        or actual!=set(policy.partitions)
        or snapshot.producers!=(policy.producer_id,) or any(b.source_sha!=m['producer_build_sha'] for b in snapshot.bars)):
        raise ValueError('signed snapshot content/count/provenance mismatch')
    check()
    return AttestedExport(snapshot,{'manifest_sha256':manifest_sha256,'snapshot_bytes_sha256':m['snapshot_sha256'],'snapshot_bytes':len(snapshot_data),'manifest_bytes':len(data),
        'snapshot_canonical_sha256':sha256(canonical_bytes({'version':1,**asdict(snapshot)})).hexdigest(),
        'trust_store_sha256':trust_store_sha256,'producer_id':m['producer_id'],'producer_build_sha':m['producer_build_sha'],
        'key_id':m['key_id'],'export_id':m['export_id'],'coherence_epoch_id':m['coherence_epoch_id'],
        'snapshot_schema_sha256':m['snapshot_schema_sha256'],'sources':m['sources'],'partitions':m['partitions'],
        'knowledge_cutoff_ns':m['knowledge_cutoff_ns'],'issued_at_ns':m['issued_at_ns'],'verification_ns':policy.verification_ns,'scope':m['scope'],
        'native_grid_truth':'NOT_ESTABLISHED_BY_CONSUMER_SIGNATURE','physical_g1':'NOT_AUTHORIZED'})
