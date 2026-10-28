"""Closed-grid requirement planning; absent event history stays blocked."""
from dataclasses import asdict,dataclass
import re
from strattester.engine.executor import _step_ms,_requirement_window
from strattester.marketdata.sync_engine import _STEP_MS

CATEGORIES=('linear','inverse','spot')
SUPPORTED={
 'linear':{'candles','mark_price','index_price','premium_index','open_interest','long_short_ratio'},
 'inverse':{'candles','mark_price','index_price','open_interest'},
 'spot':{'candles'},
}
EVENT_HISTORY={'funding','public_trades','public_trade_aggregates','orderbook_l2','liquidations'}

def integer(value,name,minimum=0):
    if type(value) is not int or value<minimum:raise ValueError(name)
    return value

def timestamp(value):
    if value is None or value=='':return None
    if type(value) is int:return integer(value,'instrument timestamp')
    if type(value) is str and re.fullmatch('[0-9]{1,16}',value):return int(value)
    raise ValueError('instrument timestamp')

@dataclass(frozen=True)
class PlannedRequirement:
    symbol:str
    dataset:str
    timeframe:str
    start_ms:int
    end_ms:int
    min_observations:int
    required:bool
    def json(self):return asdict(self)

@dataclass(frozen=True)
class HistoryPlan:
    start_ms:int
    end_exclusive_ms:int
    requirements:tuple[PlannedRequirement,...]
    blockers:tuple[str,...]

class HistoryPlanner:
    def __init__(self,max_observations=100000):
        self.max_observations=integer(max_observations,'observation budget',1)
        if self.max_observations>1000000:raise ValueError('observation budget ceiling')

    def plan(self,definition,instrument,*,start_ms,end_ms,now_ms):
        integer(start_ms,'start');integer(end_ms,'end');integer(now_ms,'now')
        if end_ms<=start_ms:raise ValueError('empty requested interval')
        category=instrument['category'];symbol=instrument['symbol'];blockers=[];requirements=[]
        if category not in CATEGORIES:raise ValueError('market category')
        launch=timestamp(instrument.get('launchTime'));delivery=timestamp(instrument.get('deliveryTime'))
        if launch is None:return HistoryPlan(start_ms,min(end_ms,now_ms),(),('UNKNOWN_LAUNCH',))
        lo=max(start_ms,launch);stop=min(end_ms,now_ms,delivery if delivery else end_ms)
        if instrument.get('marketRegion'):blockers.append('HISTORICAL_TRADING_CALENDAR_REQUIRED')
        status=instrument.get('status')
        if status!='Trading' and not (status in ('Closed','Settled','Delivering') and delivery):
            blockers.append('INSTRUMENT_NOT_ELIGIBLE')
        if stop<=lo:blockers.append('NO_CLOSED_ACTIVITY_WINDOW')
        if not definition.requirements:blockers.append('NO_DECLARED_REQUIREMENTS')
        for req in definition.requirements:
            dataset=req.dataset.value
            if dataset in EVENT_HISTORY:
                if req.required:blockers.append('HISTORICAL_CONTRACT_REQUIRED:'+dataset)
                continue
            if dataset not in SUPPORTED[category]:
                if req.required:blockers.append('UNSUPPORTED_DATASET:'+dataset)
                continue
            if dataset in ('open_interest','long_short_ratio') and any(t not in ('5m','15m','30m','1h','4h','1d') for t in (req.timeframes or ('1m',))):
                if req.required:blockers.append('UNSUPPORTED_DATASET_TIMEFRAME:'+dataset)
                continue
            for tf in req.timeframes or ('1m',):
                if tf not in _STEP_MS:
                    if req.required:blockers.append('UNSUPPORTED_TIMEFRAME:'+tf)
                    continue
                step=_step_ms(tf)
                begin,last=_requirement_window(req,lo,stop-1,tf,stop)
                count=0 if last<begin else (last-begin)//step+1
                if count<req.min_observations:
                    if req.required:blockers.append('INSUFFICIENT_LIFETIME:'+dataset+'/'+tf)
                    continue
                if count>self.max_observations:
                    if req.required:blockers.append('OBSERVATION_BUDGET:'+dataset+'/'+tf)
                    continue
                requirements.append(PlannedRequirement(symbol,dataset,tf,begin,last,req.min_observations,req.required))
        return HistoryPlan(lo,stop,tuple(requirements),tuple(sorted(set(blockers))))
