import pytest
from research.independent_timestamp_units import convert_timestamp

def test_all_units_exact_roundtrips():
    for seconds in (0,1,1_700_000_000,2**32):
        for unit in ('s','ms','us','ns'):
            value = convert_timestamp(seconds,'s',unit)
            assert convert_timestamp(value,unit,'s') == seconds

def test_lossy_downcast_fails_closed():
    for unit in ('s','ms','us'):
        with pytest.raises(ValueError, match='lossy'):
            convert_timestamp(1,'ns',unit)

def test_boolean_and_unknown_unit_rejected():
    with pytest.raises(ValueError):
        convert_timestamp(True,'s','ns')
    with pytest.raises(ValueError):
        convert_timestamp(1,'minutes','ns')
