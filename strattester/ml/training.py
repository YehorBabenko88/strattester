from __future__ import annotations
from dataclasses import dataclass
from .model import LogisticBaseline,BalancedLogisticBaseline
from .validation import walk_forward_splits
from .stability import feature_stability

@dataclass(frozen=True)
class TrainingWindowResult:
    train_start:int
    train_end:int
    test_start:int
    test_end:int
    samples:int
    accuracy:float
    brier:float
    coefficients:dict[str,float]
    positive_rate:float=0.0
    naive_accuracy:float=0.0
    naive_brier:float=0.0
    train_positive_rate:float=0.0
    probability_min:float=0.0
    probability_max:float=0.0
    probability_mean:float=0.0
    beats_naive_accuracy:bool=False
    beats_naive_brier:bool=False

@dataclass(frozen=True)
class FrozenModel:
    model:object
    trained_until:int
    feature_names:tuple[str,...]
    stable_features:tuple[str,...]
    mean_up_return:float
    mean_down_return:float

    def predict_one(self,values):
        row={k:float(values.get(k,0.0)) for k in self.feature_names}
        return self.model.predict_one(row)

@dataclass(frozen=True)
class TrainingReport:
    windows:tuple[TrainingWindowResult,...]
    stable_features:tuple[str,...]
    samples:int
    accuracy:float
    brier:float
    snapshot:FrozenModel
    positive_rate:float=0.0
    naive_accuracy:float=0.0
    naive_brier:float=0.0
    probability_min:float=0.0
    probability_max:float=0.0
    probability_mean:float=0.0
    probability_quantiles:tuple[float,...]=()
    signal_counts:tuple[tuple[float,int],...]=()
    accepted:bool=False
    rejection_reasons:tuple[str,...]=()
    regime_metrics:tuple[tuple[str,int,float,float,float],...]=()
    model_name:str='logistic'
    candidates:tuple[tuple[str,float,float],...]=()
    calibration:tuple[tuple[float,float,int],...]=()
    feature_family_usage:tuple[tuple[str,int,float,float],...]=()

def _filter(values,names):
    return {k:float(values.get(k,0.0)) for k in names}

def train_walk_forward(dataset,*,model_factory=LogisticBaseline,train_size=500,test_size=100,purge=15,min_stable_windows=3,min_direction_share=.75):
    ds=tuple(dataset)
    splits=walk_forward_splits(len(ds),train_size=train_size,test_size=test_size,purge=purge)
    if not splits: raise ValueError('not enough samples for walk-forward training')
    candidate_factories=[('logistic_l2_1e-4',model_factory)]
    if model_factory is LogisticBaseline:
        candidate_factories=[
            ('logistic_l2_1e-4',lambda:LogisticBaseline(l2=1e-4)),
            ('logistic_l2_1e-3',lambda:LogisticBaseline(l2=1e-3)),
            ('logistic_l2_1e-2',lambda:LogisticBaseline(l2=1e-2)),
            ('balanced_l2_1e-4',lambda:BalancedLogisticBaseline(l2=1e-4)),
            ('balanced_l2_1e-3',lambda:BalancedLogisticBaseline(l2=1e-3)),
            ('balanced_l2_1e-2',lambda:BalancedLogisticBaseline(l2=1e-2)),
        ]
    candidate_scores=[]
    for candidate_name,candidate_factory in candidate_factories:
        cp=[]; cy=[]
        for s in splits:
            cm=candidate_factory().fit([ds[i][0].values for i in s.train],[ds[i][1].up for i in s.train])
            for i in s.test:
                cp.append(cm.predict_one(ds[i][0].values).probability_up); cy.append(ds[i][1].up)
        ca=sum((p>=.5)==bool(y) for p,y in zip(cp,cy))/len(cp)
        cb=sum((p-y)**2 for p,y in zip(cp,cy))/len(cp)
        candidate_scores.append((candidate_name,ca,cb,candidate_factory))
    selected_name,_,_,selected_factory=min(candidate_scores,key=lambda x:(x[2],-x[1]))
    windows=[]; all_probs=[]; all_labels=[]; all_regimes=[]; coeff_windows=[]
    for s in splits:
        model=selected_factory().fit([ds[i][0].values for i in s.train],[ds[i][1].up for i in s.train])
        coeff=dict(model.coefficients())
        coeff_windows.append(coeff)
        probs=[model.predict_one(ds[i][0].values).probability_up for i in s.test]
        labels=[ds[i][1].up for i in s.test]
        train_labels=[int(ds[i][1].up) for i in s.train]
        train_rate=sum(train_labels)/len(train_labels)
        baseline_probs=[train_rate]*len(labels)
        baseline_acc=sum((p>=.5)==bool(y) for p,y in zip(baseline_probs,labels))/len(labels)
        baseline_brier=sum((p-y)**2 for p,y in zip(baseline_probs,labels))/len(labels)
        acc=sum((p>=.5)==bool(y) for p,y in zip(probs,labels))/len(probs)
        brier=sum((p-y)**2 for p,y in zip(probs,labels))/len(probs)
        all_probs.extend(probs); all_labels.extend(labels); all_regimes.extend(str(ds[i][0].regime) for i in s.test)
        windows.append(TrainingWindowResult(
            train_start=ds[s.train[0]][0].timestamp,train_end=ds[s.train[-1]][0].timestamp,
            test_start=ds[s.test[0]][0].timestamp,test_end=ds[s.test[-1]][0].timestamp,
            samples=len(s.test),accuracy=acc,brier=brier,coefficients=coeff,
            positive_rate=sum(labels)/len(labels),
            naive_accuracy=baseline_acc,
            naive_brier=baseline_brier,
            train_positive_rate=train_rate,
            probability_min=min(probs),probability_max=max(probs),
            probability_mean=sum(probs)/len(probs),
            beats_naive_accuracy=acc>baseline_acc,
            beats_naive_brier=brier<baseline_brier))
    stability=feature_stability(coeff_windows,min_windows=min_stable_windows,min_direction_share=min_direction_share)
    stable=tuple(x.name for x in stability if x.stable)
    if not stable:
        ranked=sorted(stability,key=lambda x:x.mean_importance,reverse=True)
        stable=tuple(x.name for x in ranked[:min(8,len(ranked))])
    final_rows=[_filter(f.values,stable) for f,_ in ds]
    final_model=selected_factory().fit(final_rows,[y.up for _,y in ds])
    ups=[y.future_return for _,y in ds if y.up]; downs=[y.future_return for _,y in ds if not y.up]
    step_ms=(ds[1][0].timestamp-ds[0][0].timestamp) if len(ds)>1 else 60_000
    last_feature,last_label=ds[-1]
    label_known_at=int(last_feature.timestamp)+(int(last_label.horizon_bars)+1)*int(step_ms)
    snapshot=FrozenModel(
        model=final_model,trained_until=label_known_at,feature_names=tuple(final_model.feature_names),
        stable_features=stable,
        mean_up_return=sum(ups)/len(ups) if ups else 0.0,
        mean_down_return=sum(downs)/len(downs) if downs else 0.0)
    accuracy=sum((p>=.5)==bool(y) for p,y in zip(all_probs,all_labels))/len(all_probs)
    brier=sum((p-y)**2 for p,y in zip(all_probs,all_labels))/len(all_probs)
    positive_rate=sum(all_labels)/len(all_labels)
    ordered=sorted(all_probs)
    def quantile(q):
        if not ordered:return 0.0
        pos=(len(ordered)-1)*q; lo=int(pos); hi=min(lo+1,len(ordered)-1); frac=pos-lo
        return ordered[lo]*(1-frac)+ordered[hi]*frac
    thresholds=(.55,.60,.65)
    signal_counts=tuple((x,sum(p>=x or p<=1.0-x for p in all_probs)) for x in thresholds)
    naive_accuracy=sum(w.naive_accuracy*w.samples for w in windows)/sum(w.samples for w in windows)
    naive_brier=sum(w.naive_brier*w.samples for w in windows)/sum(w.samples for w in windows)
    rejection=[]
    if accuracy<=naive_accuracy: rejection.append('oos_accuracy_not_above_naive')
    if brier>=naive_brier: rejection.append('oos_brier_not_below_naive')
    regime_buckets={}
    for p,y,regime in zip(all_probs,all_labels,all_regimes):
        regime_buckets.setdefault(regime,[]).append((p,int(y)))
    regime_metrics=[]
    for regime,items in sorted(regime_buckets.items()):
        rp=[p for p,_ in items]; ry=[y for _,y in items]
        racc=sum((p>=.5)==bool(y) for p,y in items)/len(items)
        rbrier=sum((p-y)**2 for p,y in items)/len(items)
        regime_metrics.append((regime,len(items),sum(ry)/len(ry),racc,rbrier))
    calibration=[]
    for lo in tuple(x/10 for x in range(10)):
        hi=lo+.1
        bucket=[(p,int(y)) for p,y in zip(all_probs,all_labels) if lo<=p<(hi if hi<1 else 1.0000001)]
        if bucket:
            calibration.append((sum(p for p,_ in bucket)/len(bucket),sum(y for _,y in bucket)/len(bucket),len(bucket)))
    groups={
        'momentum':('return_','price_vs_','sma'),
        'volatility':('realized_vol','vol_','range_'),
        'candle':('body_pct','upper_wick_pct','lower_wick_pct'),
        'volume_flow':('volume','turnover','delta','cvd'),
        'structure':('smc_','distance_','value_area_'),
        'external':('open_interest','long_short_ratio','funding_rate'),
        'strategy':('strategy_',),
        'forecast':('forecast_',),
    }
    all_feature_names=tuple(sorted({k for f,_ in ds for k in f.values}))
    feature_family_usage=tuple(
        (name,sum(any(k.startswith(prefix) for prefix in prefixes) for k in all_feature_names),
         sum(any(k.startswith(prefix) for prefix in prefixes) for k in stable)/max(1,len(stable)),
         sum(abs(v) for k,v in final_model.coefficients() if any(k.startswith(prefix) for prefix in prefixes)))
        for name,prefixes in groups.items())
    return TrainingReport(
        tuple(windows),stable,len(all_probs),accuracy,brier,snapshot,
        positive_rate=positive_rate,naive_accuracy=naive_accuracy,
        naive_brier=naive_brier,
        probability_min=min(all_probs),probability_max=max(all_probs),
        probability_mean=sum(all_probs)/len(all_probs),
        probability_quantiles=tuple(quantile(q) for q in (.01,.05,.25,.50,.75,.95,.99)),
        signal_counts=signal_counts,accepted=not rejection,rejection_reasons=tuple(rejection),
        regime_metrics=tuple(regime_metrics),model_name=selected_name,
        candidates=tuple((name,acc,score) for name,acc,score,_ in candidate_scores),
        calibration=tuple(calibration),feature_family_usage=feature_family_usage)

def assert_snapshot_safe_for_simulation(snapshot,*,simulation_start_ms:int,bar_ms:int,purge_bars:int):
    required_gap=int(bar_ms)*int(purge_bars)
    if int(snapshot.trained_until)+required_gap>int(simulation_start_ms):
        raise ValueError('training window overlaps simulation window or purge gap')
    return True
