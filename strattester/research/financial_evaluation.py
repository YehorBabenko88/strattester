"""Independent evaluation helpers. Simple cash returns, not log-PnL fiction."""
from dataclasses import dataclass
import math
import random
from statistics import mean
from .financial_contract import integer, finite


@dataclass(frozen=True)
class Trade:
    instrument: str
    start_ns: int
    end_ns: int
    simple_return: float
    position: int


def evaluate_ledger(trades, *, fee_bps=0., slippage_bps=0., funding_bps=0.):
    """Independent entry/exit for each disjoint label; liquidate every horizon.

    Funding is an explicit per-horizon signed cost supplied by the evaluator,
    not a fabricated exchange schedule. No leveraged fills are simulated.
    """
    costs=[finite(v,'cost') for v in (fee_bps,slippage_bps,funding_bps)]
    if any(v<0 for v in costs) or not trades:raise ValueError('costs/nonempty ledger')
    previous={};returns=[];turnover=0
    for trade in sorted(trades,key=lambda x:(x.start_ns,x.instrument)):
        integer(trade.start_ns,'start');integer(trade.end_ns,'end',1)
        if (not trade.instrument or trade.end_ns<=trade.start_ns or trade.start_ns<previous.get(trade.instrument,-1)
            or type(trade.position) is not int or trade.position not in (-1,0,1)
            or finite(trade.simple_return,'simple_return')<-1): raise ValueError('overlapping/invalid ledger')
        previous[trade.instrument]=trade.end_ns
        changed=2*abs(trade.position);turnover+=changed
        returns.append(trade.position*trade.simple_return-changed*(fee_bps+slippage_bps)/10000-abs(trade.position)*funding_bps/10000)
    if not all(math.isfinite(v) for v in returns):raise ValueError('nonfinite ledger return')
    return {'returns':returns,'turnover':turnover,'mean':mean(returns),'accounting':'simple-return, independent round trips; no leveraged portfolio simulator'}


def gaussian_scores(mu,scale,targets):
    if not targets or not len(mu)==len(scale)==len(targets):raise ValueError('distribution shape')
    if any(finite(s,'scale')<=0 for s in scale):raise ValueError('distribution scale')
    losses=[math.log(s)+.5*((finite(y,'target')-finite(m,'mu'))/s)**2+.5*math.log(2*math.pi) for m,s,y in zip(mu,scale,targets)]
    return {'nll':mean(losses),'mae':mean(abs(y-m) for y,m in zip(targets,mu)),
            'coverage_95':mean(abs(y-m)<=1.959963984540054*s for y,m,s in zip(targets,mu,scale))}


def evaluate_controls(train_x,train_y,test_x,test_y,*,seed=0):
    """Fit all baseline/negative controls only on the supplied training slice."""
    from research.alphafold_training.baselines import MeanReturnBaseline, RidgeBaseline
    integer(seed,'seed')
    if not test_y or len(test_x)!=len(test_y):raise ValueError('control shapes')
    rng=random.Random(seed); shuffled=list(train_y);rng.shuffle(shuffled)
    predictions={
        'zero':[0.]*len(test_y),
        'mean':MeanReturnBaseline().fit(train_x,train_y).predict(test_x),
        'persistence':[train_y[-1]]*len(test_y),
        'linear':RidgeBaseline().fit(train_x,train_y).predict(test_x),
        'random_signal':[rng.choice((-1.,0.,1.)) for _ in test_y],
        'label_shuffle':RidgeBaseline().fit(train_x,shuffled).predict(test_x),
        'delayed_feature':RidgeBaseline().fit(train_x,train_y).predict([train_x[-1],*test_x[:-1]]),
    }
    return {name:mean(abs(finite(y,'target')-finite(p,'prediction')) for y,p in zip(test_y,values)) for name,values in predictions.items()}
