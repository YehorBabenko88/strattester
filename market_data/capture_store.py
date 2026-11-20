"""One PostgreSQL writer for bounded original public application payloads.

No market values are recomputed. Local commit/readback does not authenticate
the public provider, qualify coverage, or grant downstream execution authority.
"""
import asyncio
from hashlib import sha256
from types import SimpleNamespace

from .raw_capture import decode_observation
from .public_trades import decode_execution_record,digest_json


_WRITER_LOCK = 0x4d44415441575231
_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_data_capture_v2 (
    observation_sha256 text PRIMARY KEY,
    observation_bytes bytea NOT NULL,
    payload_bytes bytea,
    connection_id text NOT NULL,
    observation_index bigint NOT NULL,
    UNIQUE(connection_id, observation_index)
)
;
CREATE TABLE IF NOT EXISTS market_data_execution_v1 (
    event_key text PRIMARY KEY, symbol text NOT NULL, timestamp_us numeric(19,0) NOT NULL,
    price text NOT NULL, quantity text NOT NULL, side text NOT NULL,
    trade_id text NOT NULL, content_sha256 text NOT NULL
);
CREATE TABLE IF NOT EXISTS market_data_archive_checkpoint_v1 (
    import_id text PRIMARY KEY, blob_sha256 text NOT NULL, committed_rows bigint NOT NULL,
    last_observation_sha256 text NOT NULL, total_rows bigint NOT NULL,
    last_timestamp_us text NOT NULL, last_trade_id text NOT NULL
);
"""


class CaptureStore:
    @staticmethod
    def _require_idle(connection):
        status=getattr(getattr(connection,'info',None),'transaction_status',None)
        if not isinstance(status,int) or isinstance(status,bool) or status!=0:
            raise ValueError('dedicated idle capture connection required')

    def __init__(self, connection):
        self._require_idle(connection)
        self._connection = connection
        self._lock = asyncio.Lock()
        self._closed = False

    @classmethod
    async def open(cls, dsn, *, expected_database):
        if type(expected_database) is not str or not expected_database:
            raise ValueError('explicit capture database identity required')
        import psycopg
        connection = await psycopg.AsyncConnection.connect(dsn, connect_timeout=3,
            options='-c statement_timeout=5000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=10000')
        try:
            cls._require_idle(connection)
            async with connection.transaction():
                cursor = await connection.execute('SELECT current_database()')
                if (await cursor.fetchone())[0] != expected_database:
                    raise ValueError('capture database identity mismatch')
                cursor = await connection.execute('SELECT pg_try_advisory_lock(%s)', (_WRITER_LOCK,))
                if (await cursor.fetchone())[0] is not True:
                    raise RuntimeError('market data writer already active')
                await connection.execute(_SCHEMA)
            cls._require_idle(connection)
            return cls(connection)
        except BaseException:
            await connection.close()
            raise

    async def store_capture(self, *, observation_bytes, payload_bytes):
        observation = decode_observation(observation_bytes)
        if observation['source_kind']=='ARCHIVE':raise ValueError('archive requires atomic event/checkpoint transaction')
        if payload_bytes is not None and type(payload_bytes) is not bytes:
            raise ValueError('original application payload bytes required')
        payload_sha = None if payload_bytes is None else sha256(payload_bytes).hexdigest()
        if (payload_sha != observation['payload_sha256']
                or len(payload_bytes or b'') != int(observation['payload_bytes'])):
            raise ValueError('payload differs from observation')
        digest = sha256(observation_bytes).hexdigest()
        async with self._lock:
            if self._closed:
                raise RuntimeError('capture store closed')
            self._require_idle(self._connection)
            try:
                async with self._connection.transaction():
                    await self._connection.execute(
                        'INSERT INTO market_data_capture_v2 VALUES (%s,%s,%s,%s,%s) '
                        'ON CONFLICT(observation_sha256) DO NOTHING',
                        (digest, observation_bytes, payload_bytes, observation['connection_id'],
                         int(observation['observation_index'])))
                    cursor = await self._connection.execute(
                        'SELECT observation_bytes,payload_bytes FROM market_data_capture_v2 '
                        'WHERE observation_sha256=%s', (digest,))
                    row = await cursor.fetchone()
                    if row != (observation_bytes, payload_bytes):
                        raise RuntimeError('capture readback integrity failure')
                self._require_idle(self._connection)
                # Returned only after the transaction commits. Unknown commit
                # outcomes propagate, causing RawCaptureRecorder to stop closed.
                return SimpleNamespace(
                    observation_bytes=observation_bytes, payload_bytes=payload_bytes,
                    observation_sha256=digest, observation_byte_count=len(observation_bytes),
                    payload_sha256=payload_sha, payload_byte_count=len(payload_bytes or b''),
                    journal_record_digest=digest, classification='LOCAL_UNATTESTED',
                    durability='UNKNOWN', local_content_verified=True,
                    publication_confirmed=False, native_authority_verified=False,
                    replica_eligible=False)
            except BaseException:
                self._closed=True
                try:await self._connection.close()
                except BaseException:pass
                raise

    async def close(self):
        async with self._lock:
            if not self._closed:
                self._closed = True
                await self._connection.close()

    async def archive_checkpoint(self,import_id):
        async with self._lock:
            if self._closed:raise RuntimeError('capture store closed')
            self._require_idle(self._connection)
            try:
                async with self._connection.transaction():
                    cursor=await self._connection.execute(
                        '/*archive:read_checkpoint*/ SELECT blob_sha256,committed_rows,last_observation_sha256,total_rows,last_timestamp_us,last_trade_id '
                        'FROM market_data_archive_checkpoint_v1 WHERE import_id=%s', (import_id,))
                    row=await cursor.fetchone()
                self._require_idle(self._connection)
                if row is None:return None
                return dict(zip(('blob_sha256','committed_rows','last_observation_sha256','total_rows','last_timestamp_us','last_trade_id'),row))
            except BaseException:
                self._closed=True
                try:await self._connection.close()
                except BaseException:pass
                raise

    async def store_archive_batch(self,*,observation_bytes,events):
        observation=decode_observation(observation_bytes)
        if observation['source_kind']!='ARCHIVE':raise ValueError('archive observation required')
        archive=observation['archive'];start=int(archive['start_row']);end=int(archive['end_row'])
        if type(events) is not list or any(type(event) is not dict for event in events):
            raise ValueError('archive batch records required')
        events=[dict(event) for event in events]  # Snapshot before ANY await/lock wait.
        if len(events)!=end-start or digest_json(events)!=archive['events_sha256']:
            raise ValueError('archive batch digest or row range mismatch')
        for event in events:
            decode_execution_record(event)
            if event['symbol']!=observation['instrument']['symbol']:raise ValueError('archive event instrument mismatch')
        digest=sha256(observation_bytes).hexdigest();identity=archive['import_id']
        expected_id=digest_json(dict(schema='market_data.archive-import.v1',blob_sha256=archive['blob_sha256'],symbol=observation['instrument']['symbol'],format='BYBIT_CSV_GZIP'))
        if identity!=expected_id:raise ValueError('archive source identity mismatch')
        async with self._lock:
            if self._closed:raise RuntimeError('capture store closed')
            self._require_idle(self._connection)
            try:
                async with self._connection.transaction():
                    cursor=await self._connection.execute(
                        '/*archive:read_checkpoint*/ SELECT blob_sha256,committed_rows,last_observation_sha256,total_rows,last_timestamp_us,last_trade_id '
                        'FROM market_data_archive_checkpoint_v1 WHERE import_id=%s FOR UPDATE',(identity,))
                    checkpoint=await cursor.fetchone()
                    cursor=await self._connection.execute(
                        '/*archive:read_observation*/ SELECT observation_bytes,payload_bytes FROM market_data_capture_v2 WHERE observation_sha256=%s',(digest,))
                    prior=await cursor.fetchone()
                    replay=prior is not None
                    if replay:
                        if prior!=(observation_bytes,None) or checkpoint is None or checkpoint[0]!=archive['blob_sha256'] or checkpoint[1]<end:
                            raise ValueError('archive replay checkpoint mismatch')
                    elif (checkpoint is None and start!=0) or (checkpoint is not None and
                            (checkpoint[0]!=archive['blob_sha256'] or checkpoint[1]!=start
                             or checkpoint[2]!=observation['previous_metadata_sha256'] or checkpoint[3]!=int(archive['rows']))):
                        raise ValueError('archive checkpoint cannot skip or change source')
                    elif checkpoint is None and observation['previous_metadata_sha256'] is not None:
                        raise ValueError('initial archive checkpoint cannot have predecessor')
                    for event in events:
                        values=(event['delivery_key'],event['symbol'],event['timestamp_us'],event['price'],event['quantity'],event['side'],event['trade_id'],event['content_sha256'])
                        if not replay:
                            await self._connection.execute(
                                '/*archive:insert_event*/ INSERT INTO market_data_execution_v1 '
                                '(event_key,symbol,timestamp_us,price,quantity,side,trade_id,content_sha256) '
                                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_key) DO NOTHING',values)
                        cursor=await self._connection.execute(
                            '/*archive:read_event*/ SELECT symbol,timestamp_us::text,price,quantity,side,trade_id,content_sha256 '
                            'FROM market_data_execution_v1 WHERE event_key=%s',(event['delivery_key'],))
                        if await cursor.fetchone()!=values[1:]:raise ValueError('conflicting persisted exact execution')
                    if not replay:
                        await self._connection.execute(
                            '/*archive:insert_observation*/ INSERT INTO market_data_capture_v2 VALUES (%s,%s,%s,%s,%s) '
                            'ON CONFLICT(observation_sha256) DO NOTHING',
                            (digest,observation_bytes,None,observation['connection_id'],int(observation['observation_index'])))
                        cursor=await self._connection.execute(
                            '/*archive:read_observation*/ SELECT observation_bytes,payload_bytes FROM market_data_capture_v2 WHERE observation_sha256=%s',(digest,))
                        if await cursor.fetchone()!=(observation_bytes,None):raise ValueError('archive observation readback mismatch')
                        await self._connection.execute(
                            '/*archive:write_checkpoint*/ INSERT INTO market_data_archive_checkpoint_v1 '
                            '(import_id,blob_sha256,committed_rows,last_observation_sha256,total_rows,last_timestamp_us,last_trade_id) '
                            'VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(import_id) DO UPDATE SET '
                            'committed_rows=EXCLUDED.committed_rows,last_observation_sha256=EXCLUDED.last_observation_sha256,'
                            'last_timestamp_us=EXCLUDED.last_timestamp_us,last_trade_id=EXCLUDED.last_trade_id',
                            (identity,archive['blob_sha256'],end,digest,int(archive['rows']),events[-1]['timestamp_us'],events[-1]['trade_id']))
                        cursor=await self._connection.execute(
                            '/*archive:read_checkpoint*/ SELECT blob_sha256,committed_rows,last_observation_sha256,total_rows,last_timestamp_us,last_trade_id '
                            'FROM market_data_archive_checkpoint_v1 WHERE import_id=%s',(identity,))
                        expected=(archive['blob_sha256'],end,digest,int(archive['rows']),events[-1]['timestamp_us'],events[-1]['trade_id'])
                        if await cursor.fetchone()!=expected:raise ValueError('archive checkpoint readback mismatch')
                self._require_idle(self._connection)
                return dict(import_id=identity,committed_source_rows=end,observation_sha256=digest,committed=True,
                            source_authenticity='UNKNOWN',point_in_time_availability='UNKNOWN',native_authority_verified=False)
            except BaseException:
                self._closed=True
                try:await self._connection.close()
                except BaseException:pass
                raise
