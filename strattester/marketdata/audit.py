from enum import Enum
from dataclasses import dataclass
from .instruments import InstrumentStatus

class HistoryClass(str,Enum):
    COMPLETE_HISTORY='COMPLETE_HISTORY'
    PARTIAL_HISTORY='PARTIAL_HISTORY'
    INSUFFICIENT_HISTORY='INSUFFICIENT_HISTORY'

@dataclass(frozen=True)
class CoverageAudit:
    classification:HistoryClass
    required_start:int
    required_end:int
    available_start:int|None
    available_end:int|None
    message:str=''

def classify_history(*,required_start:int,required_end:int,available_start:int|None,available_end:int|None,status:InstrumentStatus,recoverable:bool,listed_at:int|None=None)->HistoryClass:
    if available_start is None or available_end is None:
        return HistoryClass.INSUFFICIENT_HISTORY
    if listed_at is not None and required_start < listed_at:
        return HistoryClass.INSUFFICIENT_HISTORY
    complete=available_start<=required_start and available_end>=required_end
    if complete: return HistoryClass.COMPLETE_HISTORY
    if status is InstrumentStatus.DELISTED and not recoverable:
        return HistoryClass.PARTIAL_HISTORY
    return HistoryClass.INSUFFICIENT_HISTORY
