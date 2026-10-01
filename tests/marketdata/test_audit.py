from strattester.marketdata.audit import HistoryClass,classify_history
from strattester.marketdata.instruments import InstrumentStatus

def test_complete_active_history():
    assert classify_history(required_start=100,required_end=300,available_start=100,available_end=300,status=InstrumentStatus.ACTIVE,recoverable=True) is HistoryClass.COMPLETE_HISTORY

def test_unrecoverable_delisted_gap_is_partial():
    assert classify_history(required_start=100,required_end=300,available_start=150,available_end=250,status=InstrumentStatus.DELISTED,recoverable=False) is HistoryClass.PARTIAL_HISTORY

def test_missing_mandatory_dataset_is_insufficient():
    assert classify_history(required_start=100,required_end=300,available_start=None,available_end=None,status=InstrumentStatus.ACTIVE,recoverable=True) is HistoryClass.INSUFFICIENT_HISTORY

def test_history_before_listing_is_not_complete():
    assert classify_history(required_start=100,required_end=300,available_start=200,available_end=300,status=InstrumentStatus.ACTIVE,recoverable=True,listed_at=200) is HistoryClass.INSUFFICIENT_HISTORY
