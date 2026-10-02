from strattester.strategies.builtin.legacy_grid import (
    MinuteCandle, run_legacy_suite, legacy_variants
)

def test_legacy_suite_replays_history_for_all_28_variants():
    candles=[
      MinuteCandle(0,99,99.5,98.5,99),
      MinuteCandle(60_000,99,100,98.8,99.8),
      MinuteCandle(120_000,99.8,100.2,99.0,100),
      MinuteCandle(3_600_000,99,99.6,98.9,99.5),
      MinuteCandle(3_660_000,99.5,101.2,99.2,101),
    ]
    out=run_legacy_suite(candles)
    assert set(out)==set(legacy_variants())
    assert all('trades' in x and 'candles_processed' in x for x in out.values())

def test_completed_higher_timeframe_level_is_not_available_early():
    candles=[
      MinuteCandle(0,100,110,90,100),
      MinuteCandle(60_000,100,105,95,100),
      MinuteCandle(3_600_000,100,101,99,100),
    ]
    out=run_legacy_suite(candles,variant_names=('BASE',))
    levels=out['BASE']['levels']
    h=[x for x in levels if x['timeframe']=='1H' and x['level_type']=='HIGH'][0]
    assert h['price']==110
    assert h['available_at']==3_600_000
