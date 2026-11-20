"""Canonical exact public-trade DTO and complete-batch admission; no feed engine."""
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import re

MAX_FRAME_BYTES=1024*1024
MAX_BATCH_TRADES=1024
U63=2**63-1

def _decimal(value):
    if type(value) not in (Decimal,str,int):raise ValueError('exact decimal value required')
    if type(value) is not Decimal:
        text=str(value)
        if not 0<len(text)<=160 or re.fullmatch(r'[+]?(?:[0-9]+(?:[.][0-9]*)?|[.][0-9]+)(?:[eE][+-]?[0-9]+)?',text) is None:
            raise ValueError('invalid exact public numeric')
        exponent=re.split('[eE]',text)
        if len(exponent)==2 and not -4096<=int(exponent[1])<=4096:
            raise ValueError('invalid exact public numeric exponent')
        value=Decimal(text)
    if (not value.is_finite() or value<=0 or len(value.as_tuple().digits)>160
            or not -4096<=value.as_tuple().exponent<=4096):
        raise ValueError('invalid exact public numeric')
    return value

@dataclass(frozen=True)
class Trade:
    symbol: str
    ts_ms: int
    price: Decimal
    qty: Decimal
    side: str
    trade_id: str

    def __post_init__(self):
        if (type(self.symbol) is not str or re.fullmatch('[A-Z0-9]{2,30}',self.symbol) is None
                or type(self.ts_ms) is not int or not 0<self.ts_ms<=U63
                or self.side not in ('Buy','Sell')
                or type(self.trade_id) is not str or not 0<len(self.trade_id)<=128):
            raise ValueError('invalid exact execution identity')
        object.__setattr__(self,'price',_decimal(self.price))
        object.__setattr__(self,'qty',_decimal(self.qty))

def delivery_identity(trade):
    """Stable event key plus exact semantic payload digest; no commit assertion."""
    def canonical_decimal(value):
        text=format(value,'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    def digest(value):
        return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')).hexdigest()
    identity=dict(schema='market_data.execution-key.v1',exchange='bybit',category='linear',
                  symbol=trade.symbol,trade_id=trade.trade_id)
    return dict(delivery_key=digest(identity),content_sha256=digest(dict(identity,
        ts_ms=trade.ts_ms,price=canonical_decimal(trade.price),qty=canonical_decimal(trade.qty),side=trade.side)))

def decode_frame(raw):
    if not isinstance(raw,(str,bytes)):
        raise ValueError('invalid public trade frame')
    if len(raw)>MAX_FRAME_BYTES:raise ValueError('public trade frame byte limit')
    size=len(raw.encode('utf-8')) if isinstance(raw,str) else len(raw)
    if size>MAX_FRAME_BYTES:raise ValueError('public trade frame byte limit')
    def nonfinite(_):raise ValueError('nonfinite public JSON')
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate public JSON field')
            result[key] = value
        return result
    try:message=json.loads(raw,parse_constant=nonfinite,object_pairs_hook=unique_fields)
    except (ValueError,UnicodeError,RecursionError) as exc:raise ValueError('invalid public trade JSON') from exc
    if not isinstance(message,dict):raise ValueError('invalid public trade envelope')
    return message,size


def parse_trades(message,symbol,now_ms):
    """Validate every exact DTO and conflicting ID before any downstream mutation."""
    if (type(symbol) is not str or re.fullmatch('[A-Z0-9]{2,30}',symbol) is None
            or type(now_ms) is not int or not 0<now_ms<=U63
            or type(message) is not dict or message.get('topic')!='publicTrade.'+symbol):
        raise ValueError('invalid public trade envelope or clock')
    batch=message.get('data')
    if type(batch) is not list or len(batch)>MAX_BATCH_TRADES:raise ValueError('invalid public trade batch')
    trades=[]; seen={}
    for item in batch:
        if (type(item) is not dict or item.get('s')!=symbol
                or type(item.get('p')) is not str or type(item.get('v')) is not str):
            raise ValueError('invalid exact provider trade fields')
        trade=Trade(symbol,item.get('T'),item['p'],item['v'],item.get('S'),item.get('i'))
        if trade.ts_ms>now_ms+300000:raise ValueError('future public trade timestamp')
        prior=seen.setdefault(trade.trade_id,trade)
        if prior!=trade:raise ValueError('conflicting public trade identity')
        trades.append(trade)
    return trades
