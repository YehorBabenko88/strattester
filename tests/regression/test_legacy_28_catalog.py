from strattester.strategies.builtin.legacy_grid import legacy_variants

EXPECTED={
'BASE','LOW_BASE','LOW_FIRST_TOUCH','LOW_ENTRY_010','LOW_ENTRY_025','LOW_ENTRY_040','LOW_TP20','LOW_TP25','LOW_SL075','LOW_AGE_24H','LOW_AGE_3D','LOW_AGE_7D','LOW_AGE_30D',
'HIGH_BASE','HIGH_FIRST_TOUCH','HIGH_ENTRY_010','HIGH_ENTRY_025','HIGH_ENTRY_040','HIGH_TP20','HIGH_TP25','HIGH_SL075','HIGH_AGE_24H','HIGH_AGE_3D','HIGH_AGE_7D','HIGH_AGE_30D',
'REVERSAL_BASE','HIGH_SHORT','LOW_LONG'}

def test_legacy_catalog_contains_exact_28_variants():
    xs=legacy_variants()
    assert set(xs)==EXPECTED
    assert len(xs)==28

def test_entry_distance_variants_are_explicit():
    xs=legacy_variants()
    assert xs['LOW_ENTRY_010'].entry_distance==.001
    assert xs['LOW_ENTRY_025'].entry_distance==.0025
    assert xs['LOW_ENTRY_040'].entry_distance==.004
    assert xs['HIGH_ENTRY_010'].entry_distance==.001

def test_age_and_direction_variants_are_explicit():
    xs=legacy_variants()
    assert xs['LOW_AGE_24H'].max_level_age_ms==24*60*60*1000
    assert xs['HIGH_AGE_30D'].max_level_age_ms==30*24*60*60*1000
    assert xs['HIGH_SHORT'].high_direction=='SHORT'
    assert xs['LOW_LONG'].low_direction=='LONG'

def test_first_touch_variants_allow_one_entry_per_level():
    xs=legacy_variants()
    assert xs['LOW_FIRST_TOUCH'].max_entries_per_level==1
    assert xs['HIGH_FIRST_TOUCH'].max_entries_per_level==1
