"""Bounded immutable raw pages; DB insert clock is never publication/PIT.

Schema plan is review-only. No DDL, migration or old-state adoption executes here.
"""
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
import re
from .raw_capture import decode_observation

CAPTURE_SCHEMA_VERSION=3
_SCHEMA_CORE="\nCREATE TABLE public.market_data_capture_v3 (\n    observation_ordinal bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,\n    database_recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),\n    observation_sha256 text UNIQUE NOT NULL,\n    observation_bytes bytea NOT NULL,\n    payload_bytes bytea,\n    connection_id text NOT NULL,\n    observation_index bigint NOT NULL,\n    UNIQUE(connection_id, observation_index)\n)\n;\nCREATE TABLE public.market_data_execution_v2 (\n    event_key text PRIMARY KEY, symbol text NOT NULL, timestamp_us numeric(19,0) NOT NULL,\n    price text NOT NULL, quantity text NOT NULL, side text NOT NULL,\n    trade_id text NOT NULL, content_sha256 text NOT NULL\n);\nCREATE TABLE public.market_data_archive_checkpoint_v2 (\n    import_id text PRIMARY KEY, blob_sha256 text NOT NULL, committed_rows bigint NOT NULL,\n    last_observation_sha256 text NOT NULL, total_rows bigint NOT NULL,\n    last_timestamp_us text NOT NULL, last_trade_id text NOT NULL\n);\n"
CAPTURE_LAYOUT_SHA256=sha256(_SCHEMA_CORE.encode('utf-8')).hexdigest()
_SCHEMA_CHECK_SQL='/*capture:schema_check*/ SELECT schema_version,layout_sha256 FROM public.market_data_schema_v3 WHERE singleton=TRUE'

@dataclass(frozen=True)
class CaptureSchemaPlan:
    version: int
    layout_sha256: str
    ddl_sql: str
    execution_status: str='NOT_EXECUTED'
    existing_data_adoption: bool=False
    rollback_policy: str='Select prior release and retain both namespaces/WAL for reconciliation; no deletion or automatic rollback.'

def capture_schema_plan():
    control=('CREATE TABLE public.market_data_schema_v3 (singleton boolean PRIMARY KEY CHECK(singleton), schema_version integer NOT NULL CHECK(schema_version=3), layout_sha256 text NOT NULL);\n'
        +"INSERT INTO public.market_data_schema_v3 VALUES (TRUE,3,'"+CAPTURE_LAYOUT_SHA256+"');\n")
    return CaptureSchemaPlan(3,CAPTURE_LAYOUT_SHA256,_SCHEMA_CORE+control)

@dataclass(frozen=True)
class CaptureReadRecord:
    ordinal: str
    database_recorded_at: str
    observation_sha256: str
    observation_bytes: bytes
    payload_bytes: bytes | None
    payload_sha256: str | None
    source_kind: str
    frame_metadata_sha256: str | None
    previous_metadata_sha256: str | None
    archive_blob_sha256: str | None
    clock_basis: str='DB_INSERT_CLOCK'
    link_resolution: str='UNKNOWN'
    blob_resolution: str='NOT_READ'

@dataclass(frozen=True)
class CaptureReadPage:
    records: tuple
    next_ordinal: str
    has_more: bool
    cursor_scope: str='STORAGE_ORDINAL_NOT_PROVIDER_SEQUENCE'
    snapshot_scope: str='THIS_READ_TRANSACTION'
    complete_prefix: bool=False
    resume_is_lossless: bool=False
    inspection_only: bool=True
    source_authenticity: str='NOT_EVALUATED'
    source_completeness: str='NOT_EVALUATED'
    publication_status: str='UNKNOWN'
    point_in_time_availability: str='UNKNOWN'

def page_request(after_ordinal,limit):
    if (type(after_ordinal) is not str or re.fullmatch('0|[1-9][0-9]{0,18}',after_ordinal) is None
            or int(after_ordinal)>2**63-1 or type(limit) is not int or not 1<=limit<=100):
        raise ValueError('bounded canonical storage cursor required')
    return int(after_ordinal),limit

_PAGE_SQL="""/*capture:read_page*/ WITH bounded AS (
 SELECT observation_ordinal,database_recorded_at,observation_sha256,observation_bytes,payload_bytes
 FROM public.market_data_capture_v3 WHERE observation_ordinal>%s
 ORDER BY observation_ordinal LIMIT %s
), measured AS (SELECT *,sum(octet_length(observation_bytes)+COALESCE(octet_length(payload_bytes),0)) OVER() AS batch_bytes FROM bounded)
SELECT observation_ordinal,database_recorded_at,observation_sha256,
 CASE WHEN batch_bytes<=8388608 AND octet_length(observation_bytes)<=16384 AND COALESCE(octet_length(payload_bytes),0)<=1048576 THEN observation_bytes ELSE NULL END,
 CASE WHEN batch_bytes<=8388608 AND octet_length(observation_bytes)<=16384 AND COALESCE(octet_length(payload_bytes),0)<=1048576 THEN payload_bytes ELSE NULL END
FROM measured ORDER BY observation_ordinal"""

def decode_page(rows,after_ordinal,limit):
    after,_=page_request(after_ordinal,limit)
    if type(rows) not in (list,tuple) or len(rows)>limit+1:raise ValueError('read page row budget exceeded')
    records=[];previous=after;total=0
    for row in rows:
        if type(row) not in (tuple,list) or len(row)!=5:raise ValueError('invalid read page row')
        ordinal,recorded,digest,raw,payload=row
        if type(ordinal) is not int or not previous<ordinal<=2**63-1:raise ValueError('storage cursor regression')
        if type(recorded) is not datetime or recorded.tzinfo is None or recorded.utcoffset() is None:raise ValueError('untyped database clock')
        if type(raw) is not bytes or not 0<len(raw)<=16384:raise ValueError('raw page metadata/byte budget refused')
        if payload is not None and (type(payload) is not bytes or len(payload)>1048576):raise ValueError('raw page payload budget refused')
        total+=len(raw)+len(payload or b'')
        if total>8388608:raise ValueError('raw page byte budget refused')
        if type(digest) is not str or sha256(raw).hexdigest()!=digest:raise ValueError('raw observation digest drift')
        value=decode_observation(raw);actual=None if payload is None else sha256(payload).hexdigest()
        if actual!=value['payload_sha256'] or len(payload or b'')!=int(value['payload_bytes']):raise ValueError('raw payload digest drift')
        archive=value['archive']
        records.append(CaptureReadRecord(str(ordinal),recorded.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z'),digest,raw,payload,actual,value['source_kind'],value['frame_metadata_sha256'],value['previous_metadata_sha256'],None if archive is None else archive['blob_sha256']))
        previous=ordinal
    selected=tuple(records[:limit])
    return CaptureReadPage(selected,after_ordinal if not selected else selected[-1].ordinal,len(records)>limit)
