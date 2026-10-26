"""Independent evaluation helpers. Simple cash returns, not log-PnL fiction."""
from dataclasses import dataclass
import math
import random
from bisect import bisect_left
from statistics import mean
from .financial_contract import integer, finite


@dataclass(frozen=True)
class Trade:
    instrument: str
    start_ns: int
    end_ns: int
    simple_return: float
    position: int


def evaluate_ledger(trades, *, fee_bps=0., slippage_bps=0., funding_bps=0., funding_windows=None):
    """Independent entry/exit for each disjoint label; liquidate every horizon.

    Funding is an explicit flat nonnegative per-horizon charge supplied by the evaluator,
    not a fabricated exchange schedule. No leveraged fills are simulated.
    Opt-in funding_windows replaces that flat charge with bounded software-only
    signed settlement bps on fixed entry notional; it supplies no producer proof.
    """
    trades=list(trades)
    costs=[finite(v,'cost') for v in (fee_bps,slippage_bps,funding_bps)]
    if any(v<0 for v in costs) or not trades:raise ValueError('costs/nonempty ledger')
    if funding_windows is not None and funding_bps != 0:
        raise ValueError('cannot combine flat funding charge and funding events')
    previous={};returns=[];turnover=0
    for trade in sorted(trades,key=lambda x:(x.start_ns,x.instrument)):
        integer(trade.start_ns,'start');integer(trade.end_ns,'end',1)
        if (not trade.instrument or trade.end_ns<=trade.start_ns or trade.start_ns<previous.get(trade.instrument,-1)
            or type(trade.position) is not int or trade.position not in (-1,0,1)
            or finite(trade.simple_return,'simple_return')<-1): raise ValueError('overlapping/invalid ledger')
        previous[trade.instrument]=trade.end_ns
        changed=2*abs(trade.position);turnover+=changed
        returns.append(trade.position*trade.simple_return-changed*(fee_bps+slippage_bps)/10000-abs(trade.position)*funding_bps/10000)
    if funding_windows is not None:
        from .financial_funding import funding_adjustments
        adjustments=funding_adjustments(sorted(trades,key=lambda x:(x.start_ns,x.instrument)),funding_windows)
        returns=[value+adjustment for value,adjustment in zip(returns,adjustments)]
    if not all(math.isfinite(v) for v in returns):raise ValueError('nonfinite ledger return')
    report={'returns':returns,'turnover':turnover,'mean':mean(returns),'accounting':'simple-return, independent round trips; no leveraged portfolio simulator'}
    if funding_windows is not None:
        report['funding_status']='RESEARCH_CONTRACT_ONLY_NOT_PRODUCER_AUTHENTICATED'
    return report


def gaussian_scores(mu,scale,targets):
    if not targets or not len(mu)==len(scale)==len(targets):raise ValueError('distribution shape')
    if any(finite(s,'scale')<=0 for s in scale):raise ValueError('distribution scale')
    losses=[];errors=[]
    for m,s,y in zip(mu,scale,targets):
        error=abs(finite(y,'target')-finite(m,'mu'));z=error/s
        loss=math.log(s)+.5*z*z+.5*math.log(2*math.pi)
        if not math.isfinite(error) or not math.isfinite(loss):raise ValueError('nonfinite distribution score')
        errors.append(error);losses.append(loss)
    return {'nll':mean(losses),'mae':mean(errors),
            'coverage_95':mean(abs(y-m)<=1.959963984540054*s for y,m,s in zip(targets,mu,scale))}


def delayed_features(history_x,history_events,query_events):
    """Latest strictly earlier feature row from the identical market/series key."""
    if len(history_x)!=len(history_events) or not history_x:raise ValueError('history shape')
    groups={};seen=set()
    for row,(identity,timestamp) in zip(history_x,history_events):
        integer(timestamp,'feature time')
        if not isinstance(identity,str) or not identity or (identity,timestamp) in seen:
            raise ValueError('invalid/duplicate feature identity')
        seen.add((identity,timestamp));groups.setdefault(identity,[]).append((timestamp,row))
    for values in groups.values():values.sort(key=lambda item:item[0])
    result=[]
    for identity,timestamp in query_events:
        integer(timestamp,'query time')
        values=groups.get(identity,[])
        index=bisect_left([t for t,row in values],timestamp)-1
        if index<0:raise ValueError('BLOCKED: no strictly prior same-series control feature')
        result.append(values[index][1])
    return result


def evaluate_controls(train_x,train_y,test_x,test_y,*,train_events,test_events,seed=0,history_x=None,history_events=None):
    """Fit all baseline/negative controls only on the supplied training slice."""
    from research.alphafold_training.baselines import MeanReturnBaseline, RidgeBaseline
    integer(seed,'seed')
    if (not test_y or len(test_x)!=len(test_y) or len(train_x)!=len(train_events)
        or len(test_x)!=len(test_events)):raise ValueError('control shapes')
    if history_x is None:
        history_x=[*train_x,*test_x];history_events=[*train_events,*test_events]
    delayed=delayed_features(history_x,history_events,test_events)
    rng=random.Random(seed); shuffled=list(train_y);rng.shuffle(shuffled)
    predictions={
        'zero':[0.]*len(test_y),
        'mean':MeanReturnBaseline().fit(train_x,train_y).predict(test_x),
        # The financial adapter's first channel is the target instrument's
        # currently observed return, available without any future label.
        'persistence':[row[0] for row in test_x],
        'linear':RidgeBaseline().fit(train_x,train_y).predict(test_x),
        'random_signal':[rng.choice((-1.,0.,1.)) for _ in test_y],
        'label_shuffle':RidgeBaseline().fit(train_x,shuffled).predict(test_x),
        'delayed_feature':RidgeBaseline().fit(train_x,train_y).predict(delayed),
    }
    return {name:mean(abs(finite(y,'target')-finite(p,'prediction')) for y,p in zip(test_y,values)) for name,values in predictions.items()}
