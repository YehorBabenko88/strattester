"""One PostgreSQL writer for bounded original public application payloads.

No market values are recomputed. Local commit/readback does not authenticate
the public provider, qualify coverage, or grant downstream execution authority.
"""
import asyncio
from hashlib import sha256
from types import SimpleNamespace

from .raw_capture import decode_observation


_WRITER_LOCK = 0x4d44415441575231
_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_data_capture_v1 (
    observation_sha256 text PRIMARY KEY,
    observation_bytes bytea NOT NULL,
    payload_bytes bytea,
    connection_id text NOT NULL,
    observation_index bigint NOT NULL,
    UNIQUE(connection_id, observation_index)
)
"""


class CaptureStore:
    def __init__(self, connection):
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
            cursor = await connection.execute('SELECT current_database()')
            if (await cursor.fetchone())[0] != expected_database:
                raise ValueError('capture database identity mismatch')
            cursor = await connection.execute('SELECT pg_try_advisory_lock(%s)', (_WRITER_LOCK,))
            if (await cursor.fetchone())[0] is not True:
                raise RuntimeError('market data writer already active')
            await connection.execute(_SCHEMA)
            await connection.commit()
            return cls(connection)
        except BaseException:
            await connection.close()
            raise

    async def store_capture(self, *, observation_bytes, payload_bytes):
        observation = decode_observation(observation_bytes)
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
            async with self._connection.transaction():
                await self._connection.execute(
                    'INSERT INTO market_data_capture_v1 VALUES (%s,%s,%s,%s,%s) '
                    'ON CONFLICT(observation_sha256) DO NOTHING',
                    (digest, observation_bytes, payload_bytes, observation['connection_id'],
                     int(observation['observation_index'])))
                cursor = await self._connection.execute(
                    'SELECT observation_bytes,payload_bytes FROM market_data_capture_v1 '
                    'WHERE observation_sha256=%s', (digest,))
                row = await cursor.fetchone()
                if row != (observation_bytes, payload_bytes):
                    raise RuntimeError('capture readback integrity failure')
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

    async def close(self):
        async with self._lock:
            if not self._closed:
                self._closed = True
                await self._connection.close()
