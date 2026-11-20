"""Bounded public trade capture, with persistence before any downstream use.

Reuses the canonical decoder and RawCaptureRecorder, without strategy, price
aggregation, mathematical feature pipelines, or alternate market writers.
"""
import asyncio
import json
import re
import time
from math import isfinite

from .public_trades import decode_frame, parse_trades, MAX_FRAME_BYTES
from .raw_capture import RawCaptureRecorder, RawCaptureProfile, RawCaptureError


PUBLIC_ENDPOINT = 'wss://stream.bybit.com/v5/public/linear'


async def public_connection(endpoint):
    if endpoint != PUBLIC_ENDPOINT:
        raise ValueError('only the canonical public provider endpoint is supported')
    import websockets
    return websockets.connect(endpoint, max_size=MAX_FRAME_BYTES, max_queue=4,
                              open_timeout=10, close_timeout=3, ping_interval=20,
                              ping_timeout=10, proxy=None)


class PublicTradeCollector:
    def __init__(self, sink, *, symbol, source_revision, connector=public_connection,
                 clock_ms=lambda: int(time.time() * 1000), max_frames=4, persist_timeout=20):
        if type(symbol) is not str or re.fullmatch('[A-Z0-9]{2,30}', symbol) is None:
            raise ValueError('invalid capture instrument')
        if type(max_frames) is not int or not 1 <= max_frames <= 4:
            raise ValueError('bounded capture requires one to four application frames')
        if (type(source_revision) is not str
                or re.fullmatch('[0-9a-f]{40}', source_revision) is None):
            raise ValueError('exact producer source revision required')
        self.symbol = symbol
        self.connector = connector
        self.clock_ms = clock_ms
        self.max_frames = max_frames
        if (type(persist_timeout) not in (int, float) or not isfinite(persist_timeout)
                or not 0 < persist_timeout <= 20):
            raise ValueError('invalid persistence deadline')
        self.persist_timeout = persist_timeout
        self.recorder = RawCaptureRecorder(
            sink, instrument={'exchange': 'bybit', 'category': 'linear',
                              'symbol': symbol, 'instrument_version': '1'},
            producer_source_revision=source_revision,
            source_kind='PUBLIC_PROVIDER_OBSERVED_UNAUTHENTICATED', endpoint=PUBLIC_ENDPOINT,
            profile=RawCaptureProfile(16, 4194304, MAX_FRAME_BYTES, 16384, 2))

    async def _persist(self, operation):
        return await asyncio.wait_for(operation, timeout=self.persist_timeout)

    async def run(self):
        self.recorder.begin_connection()
        accepted = 0
        subscribed = False
        try:
            connection = await self.connector(PUBLIC_ENDPOINT)
            async with connection as websocket:
                await websocket.send(json.dumps({'op': 'subscribe', 'args': ['publicTrade.' + self.symbol]}))
                for _ in range(self.max_frames):
                    raw = await asyncio.wait_for(websocket.recv(), timeout=30)
                    reference = await self._persist(self.recorder.frame(raw))
                    try:
                        message, _ = decode_frame(raw)
                        if message.get('op') == 'subscribe':
                            if subscribed or message.get('success') is not True:
                                raise ValueError('public subscription refused')
                            subscribed = True
                            continue
                        if not subscribed:
                            raise ValueError('public trades arrived before subscription acknowledgement')
                        trades = parse_trades(message, self.symbol, self.clock_ms())
                    except ValueError:
                        await self._persist(self.recorder.gap('frame_invalid', reference))
                        raise
                    await self._persist(self.recorder.validated(reference))
                    accepted += len(trades)
                await self._persist(self.recorder.disconnect('normal_stop'))
        except asyncio.CancelledError:
            await self._persist(self.recorder.disconnect('cancelled'))
            raise
        except RawCaptureError:
            # Never reconnect around storage uncertainty or capacity refusal.
            raise
        except BaseException:
            await self._persist(self.recorder.disconnect('transport_error'))
            raise
        return {'schema': 'market_data.capture.receipt.v1',
                'accepted_trade_observations': accepted,
                'capture': self.recorder.metrics(), 'coverage': 'UNKNOWN',
                'source_authenticity': 'NOT_INDEPENDENTLY_VERIFIED',
                'execution_authority': False, 'trading_authorized': False}
