"""Admission bounds for the existing public-trade collector; no feed engine."""
import json
import math

from dataclasses import dataclass

@dataclass(frozen=True)
class Trade:
    symbol: str
    ts_ms: int
    price: float
    qty: float
    side: str
    trade_id: str = ""

MAX_FRAME_BYTES=1024*1024
MAX_BATCH_TRADES=1024
MAX_ACK_FRAMES=2000
MAX_ACK_BYTES=4*1024*1024
MAX_OPEN_MINUTES=1024
PERSIST_TIMEOUT_SECONDS=20


def decode_frame(raw):
    if not isinstance(raw,(str,bytes)):
        raise ValueError('invalid public trade frame')
    if len(raw)>MAX_FRAME_BYTES:raise ValueError('public trade frame byte limit')
    size=len(raw.encode('utf-8')) if isinstance(raw,str) else len(raw)
    if size>MAX_FRAME_BYTES:raise ValueError('public trade frame byte limit')
    def nonfinite(_):raise ValueError('nonfinite public JSON')
    try:message=json.loads(raw,parse_constant=nonfinite)
    except (ValueError,UnicodeError,RecursionError) as exc:raise ValueError('invalid public trade JSON') from exc
    if not isinstance(message,dict):raise ValueError('invalid public trade envelope')
    return message,size


def parse_trades(message,symbol,now_ms):
    """Validate the complete batch before any continuity/aggregate mutation."""
    if message.get('topic')!='publicTrade.'+symbol:raise ValueError('unsubscribed trade topic')
    batch=message.get('data')
    if not isinstance(batch,list) or len(batch)>MAX_BATCH_TRADES:raise ValueError('invalid public trade batch')
    trades=[]
    for item in batch:
        if not isinstance(item,dict) or ('s' in item and item['s']!=symbol):raise ValueError('invalid public trade symbol')
        stamp=item.get('T')
        if isinstance(stamp,str) and 0<len(stamp)<=20 and stamp.isascii() and stamp.isdecimal():stamp=int(stamp)
        if type(stamp) is not int or stamp<=0 or stamp>now_ms+300000:raise ValueError('invalid public trade timestamp')
        values=[]
        for key in ('p','v'):
            value=item.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float,str)) or (isinstance(value,str) and len(value)>64):raise ValueError('invalid public trade numeric')
            try:value=float(value)
            except (ValueError,TypeError,OverflowError) as exc:raise ValueError('invalid public trade numeric') from exc
            if not math.isfinite(value) or value<=0:raise ValueError('invalid public trade numeric')
            values.append(value)
        side=item.get('S');trade_id=item.get('i')
        if side not in ('Buy','Sell') or not isinstance(trade_id,str) or not 0<len(trade_id)<=128:raise ValueError('invalid public trade side or identity')
        trades.append(Trade(symbol,stamp,values[0],values[1],side,trade_id))
    return trades


def validated_tick(value):
    if isinstance(value,bool):raise ValueError('invalid public trade tick')
    try:value=float(value)
    except (ValueError,TypeError,OverflowError) as exc:raise ValueError('invalid public trade tick') from exc
    if not math.isfinite(value) or value<=0:raise ValueError('invalid public trade tick')
    return value
