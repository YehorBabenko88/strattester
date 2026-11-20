"""Pure SQL-session/page models only: no real DB, migration, network or process."""
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from types import SimpleNamespace
import hashlib,sys
import pytest
from market_data.capture_store import CaptureStore
from market_data.capture_read_model import capture_schema_plan,CAPTURE_LAYOUT_SHA256
from test_capture_store import recorder
from test_capture_runtime import Sink

class Connection:
    def __init__(self,rows=(),schema=(3,None)):
        self.info=SimpleNamespace(transaction_status=0);self.rows=list(rows);self.schema=(3,CAPTURE_LAYOUT_SHA256) if schema==(3,None) else schema;self.closed=False;self.calls=[];self.pending=None
    @asynccontextmanager
    async def transaction(self):
        assert self.info.transaction_status==0;self.info.transaction_status=2
        try:yield self
        finally:self.info.transaction_status=0
    async def execute(self,sql,args=()):
        assert self.info.transaction_status==2
        assert not sql.lstrip().upper().startswith(('CREATE','ALTER','DROP','INSERT INTO PUBLIC.MARKET_DATA_SCHEMA')),'runtime cannot execute schemaDDL/adoption'
        self.calls.append((sql,args))
        if 'current_database()'in sql:self.pending=('fixture',)
        elif 'capture:schema_check'in sql:self.pending=self.schema
        elif 'pg_try_advisory_lock'in sql:self.pending=(True,)
        return self
    async def fetchone(self):return self.pending
    async def fetchall(self):return self.rows
    async def close(self):self.closed=True

async def row(ordinal=1):
    sink=Sink();capture=recorder(sink);capture.begin_connection();await capture.frame(b'exact-raw')
    raw,payload=sink.rows[0]
    return (ordinal,datetime(2026,11,20,tzinfo=timezone.utc),hashlib.sha256(raw).hexdigest(),raw,payload)

def test_schema_plan_is_review_only_without_existing_data_adoption():
    plan=capture_schema_plan()
    assert plan.version==3 and plan.layout_sha256==CAPTURE_LAYOUT_SHA256
    assert 'clock_timestamp()'in plan.ddl_sql and 'GENERATED ALWAYS AS IDENTITY'in plan.ddl_sql
    assert plan.execution_status=='NOT_EXECUTED' and plan.existing_data_adoption is False
    assert 'DROP TABLE'not in plan.rollback_policy and 'market_data_capture_v2'not in plan.ddl_sql

@pytest.mark.asyncio
async def test_open_requires_manual_schema_and_never_executes_ddl(monkeypatch):
    for schema,accepted in (((3,None),True),(None,False),((2,'a'*64),False),((3,'a'*64),False)):
        connection=Connection(schema=schema)
        async def connect(*args,**kwargs):return connection
        monkeypatch.setitem(sys.modules,'psycopg',SimpleNamespace(AsyncConnection=SimpleNamespace(connect=connect)))
        if accepted:await CaptureStore.open('synthetic',expected_database='fixture')
        else:
            with pytest.raises(ValueError):await CaptureStore.open('synthetic',expected_database='fixture')
            assert connection.closed
        assert connection.info.transaction_status==0

@pytest.mark.asyncio
async def test_page_preserves_storage_holes_raw_sha_links_and_unknown_authority():
    rows=[await row(1),await row(9),await row(11)];connection=Connection(rows);store=CaptureStore(connection)
    page=await store.read_capture_page(after_ordinal='0',limit=2)
    assert [record.ordinal for record in page.records]==['1','9'] and page.next_ordinal=='9' and page.has_more is True
    assert page.cursor_scope=='STORAGE_ORDINAL_NOT_PROVIDER_SEQUENCE'
    assert page.publication_status==page.point_in_time_availability=='UNKNOWN'
    assert page.source_authenticity=='NOT_EVALUATED'
    assert all(record.clock_basis=='DB_INSERT_CLOCK' and record.source_kind=='SYNTHETIC' for record in page.records)
    assert page.records[0].payload_bytes==b'exact-raw' and page.records[0].link_resolution=='UNKNOWN'
    assert connection.info.transaction_status==0 and not connection.closed
    with pytest.raises(Exception):page.records[0].ordinal='2'

@pytest.mark.asyncio
@pytest.mark.parametrize('change',[{'observation':None},{'sha':'0'*64},{'payload':b'changed'},{'ordinal':True}])
async def test_page_corruption_or_server_budget_sentinel_refuses_all(change):
    values=list(await row());indexes={'observation':3,'sha':2,'payload':4,'ordinal':0}
    for key,value in change.items():values[indexes[key]]=value
    connection=Connection([tuple(values)]);store=CaptureStore(connection)
    with pytest.raises(ValueError):await store.read_capture_page(after_ordinal='0',limit=1)
    assert connection.closed

@pytest.mark.asyncio
@pytest.mark.parametrize('after,limit',[('01',1),('0',True),('0',101),('9223372036854775808',1),(0,1)])
async def test_page_input_refuses_before_connection(after,limit):
    connection=Connection();store=CaptureStore(connection)
    with pytest.raises(ValueError):await store.read_capture_page(after_ordinal=after,limit=limit)
    assert connection.calls==[] and not connection.closed

@pytest.mark.asyncio
async def test_legacy_wal_target_never_adopted_or_acknowledged(tmp_path):
    from market_data.archive_import import ArchiveImporter
    from market_data.segment_wal import SegmentWAL
    wal=SegmentWAL(tmp_path/'legacy-wal');await wal.append(dict(schema='market_data.archive-wal.v1',observation={},events=[]))
    class Unused:
        async def store_archive_batch(self,**kwargs):raise AssertionError('NO_LEGACY_ADOPTION')
    importer=ArchiveImporter(tmp_path,Unused(),wal,source_revision='a'*40)
    with pytest.raises(ValueError):await importer.recover()
    assert importer.failed and len(wal.recover())==1

@pytest.mark.asyncio
async def test_lower_uncommitted_ordinal_cannot_be_claimed_complete_or_lossless():
    # T1 reserves 1, T2 reserves/commits 2 before T1. Snapshot sees only 2.
    connection=Connection([await row(2)]);store=CaptureStore(connection)
    first=await store.read_capture_page(after_ordinal='0',limit=2)
    assert first.next_ordinal=='2' and not first.has_more
    assert first.complete_prefix is False and first.resume_is_lossless is False and first.inspection_only is True
    # Later T1 commits: resuming >2 misses 1; only a fresh inspection includes it.
    connection.rows=[]
    resumed=await store.read_capture_page(after_ordinal=first.next_ordinal,limit=2)
    assert resumed.records==() and resumed.complete_prefix is False
    connection.rows=[await row(1),await row(2)]
    fresh=await store.read_capture_page(after_ordinal='0',limit=2)
    assert [r.ordinal for r in fresh.records]==['1','2']
    assert fresh.resume_is_lossless is False

@pytest.mark.asyncio
async def test_reserved_ranges_and_rollback_holes_do_not_imply_provider_loss():
    # Reserved/cache allocation or rollback may leave gaps; no provider inference.
    connection=Connection([await row(1),await row(33)]);store=CaptureStore(connection)
    page=await store.read_capture_page(after_ordinal='0',limit=2)
    assert [r.ordinal for r in page.records]==['1','33']
    assert page.source_completeness=='NOT_EVALUATED'
    assert page.complete_prefix is page.resume_is_lossless is False
