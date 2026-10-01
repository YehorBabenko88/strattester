from strattester.marketdata.datasets import DatasetKind, supports_historical
from strattester.marketdata.schema import SCHEMA_SQL
from strattester.strategies.base import DataRequirement

def test_rich_datasets_have_explicit_contracts():
    expected={DatasetKind.CANDLES,DatasetKind.MARK_PRICE,DatasetKind.INDEX_PRICE,DatasetKind.PREMIUM_INDEX,DatasetKind.OPEN_INTEREST,DatasetKind.FUNDING,DatasetKind.LONG_SHORT_RATIO,DatasetKind.PUBLIC_TRADES}
    assert expected.issubset(set(DatasetKind))
    assert supports_historical(DatasetKind.PUBLIC_TRADES)
    assert not supports_historical(DatasetKind.ORDERBOOK_L2)
    req=DataRequirement(DatasetKind.OPEN_INTEREST,('5m',))
    assert req.dataset is DatasetKind.OPEN_INTEREST

def test_schema_contains_rich_history_tables():
    for table in ('mark_prices','index_prices','premium_index','open_interest','funding','long_short_ratio','public_trade_aggregates'):
        assert f'CREATE TABLE IF NOT EXISTS {table}' in SCHEMA_SQL
