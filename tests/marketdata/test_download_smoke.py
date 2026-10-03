from strattester.marketdata.download_smoke import validate_candle_smoke

def test_candle_smoke_validation_requires_contiguous_unique_rows():
    rows=[
      ['120000','2','3','1','2.5','10','20'],
      ['60000','1','2','.5','1.5','9','15'],
    ]
    r=validate_candle_smoke(rows,60000,120000)
    assert r.ok and r.count==2 and r.duplicates==0 and r.gaps==0

def test_candle_smoke_validation_rejects_gap():
    rows=[['60000','1','2','.5','1.5','9','15'],['180000','2','3','1','2.5','10','20']]
    assert not validate_candle_smoke(rows,60000,180000).ok
