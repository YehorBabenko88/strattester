import pytest
from research.independent_series_identity import validate_series_identity

def test_same_series_identity():
    rows=[('Bybit','linear','BTCUSDT','1m',0,60),('Bybit','linear','BTCUSDT','1m',60,120)]
    assert validate_series_identity(rows)==('Bybit','linear','BTCUSDT','1m')

@pytest.mark.parametrize('changed',[
    ('Bybit','linear','ETHUSDT','1m',60,120),
    ('Bybit','linear','BTCUSDT','5m',60,120),
    ('Other','linear','BTCUSDT','1m',60,120)])
def test_mixed_series_rejected(changed):
    with pytest.raises(ValueError,match='mixed'):
        validate_series_identity([('Bybit','linear','BTCUSDT','1m',0,60),changed])

def test_duplicate_series_timestamp_rejected():
    row=('Bybit','linear','BTCUSDT','1m',0,60)
    with pytest.raises(ValueError,match='duplicate'):
        validate_series_identity([row,row])
