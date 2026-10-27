import pytest
from research.independent_event_clock import validate_event_clock

def test_valid_out_of_order_ingestion_rows():
    rows=[dict(event_id='a',event_ns=10,ingest_ns=30,available_ns=40),
          dict(event_id='b',event_ns=20,ingest_ns=25,available_ns=35)]
    assert validate_event_clock(rows,40)

@pytest.mark.parametrize('row',[
    dict(event_id='a',event_ns=20,ingest_ns=10,available_ns=30),
    dict(event_id='a',event_ns=10,ingest_ns=30,available_ns=20),
    dict(event_id='a',event_ns=10,ingest_ns=20,available_ns=41)])
def test_noncausal_clock_rejected(row):
    with pytest.raises(ValueError):
        validate_event_clock([row],40)

def test_duplicate_event_rejected():
    row=dict(event_id='x',event_ns=10,ingest_ns=20,available_ns=30)
    with pytest.raises(ValueError):
        validate_event_clock([row,row],40)
