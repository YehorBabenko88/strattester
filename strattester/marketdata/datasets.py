from enum import Enum

class DatasetKind(str, Enum):
    CANDLES='candles'
    MARK_PRICE='mark_price'
    INDEX_PRICE='index_price'
    PREMIUM_INDEX='premium_index'
    OPEN_INTEREST='open_interest'
    FUNDING='funding'
    LONG_SHORT_RATIO='long_short_ratio'
    PUBLIC_TRADES='public_trades'
    PUBLIC_TRADE_AGGREGATES='public_trade_aggregates'
    ORDERBOOK_L2='orderbook_l2'
    LIQUIDATIONS='liquidations'

_UNAVAILABLE_HISTORICAL={DatasetKind.ORDERBOOK_L2,DatasetKind.LIQUIDATIONS}

def supports_historical(dataset:DatasetKind)->bool:
    return dataset not in _UNAVAILABLE_HISTORICAL
