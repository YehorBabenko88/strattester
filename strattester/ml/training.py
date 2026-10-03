from __future__ import annotations
from dataclasses import dataclass
from .model import LogisticBaseline
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

def _filter(values,names):
    return {k:float(values.get(k,0.0)) for k in names}

def train_walk_forward(dataset,*,model_factory=LogisticBaseline,train_size=500,test_size=100,purge=15,min_stable_windows=3,min_direction_share=.75):
    ds=tuple(dataset)
    splits=walk_forward_splits(len(ds),train_size=train_size,test_size=test_size,purge=purge)
    if not splits: raise ValueError('not enough samples for walk-forward training')
    windows=[]; all_probs=[]; all_labels=[]; coeff_windows=[]
    for s in splits:
        model=model_factory().fit([ds[i][0].values for i in s.train],[ds[i][1].up for i in s.train])
        coeff=dict(model.coefficients())
        coeff_windows.append(coeff)
        probs=[model.predict_one(ds[i][0].values).probability_up for i in s.test]
        labels=[ds[i][1].up for i in s.test]
        acc=sum((p>=.5)==bool(y) for p,y in zip(probs,labels))/len(probs)
        brier=sum((p-y)**2 for p,y in zip(probs,labels))/len(probs)
        all_probs.extend(probs); all_labels.extend(labels)
        windows.append(TrainingWindowResult(
            train_start=ds[s.train[0]][0].timestamp,train_end=ds[s.train[-1]][0].timestamp,
            test_start=ds[s.test[0]][0].timestamp,test_end=ds[s.test[-1]][0].timestamp,
            samples=len(s.test),accuracy=acc,brier=brier,coefficients=coeff))
    stability=feature_stability(coeff_windows,min_windows=min_stable_windows,min_direction_share=min_direction_share)
    stable=tuple(x.name for x in stability if x.stable)
    if not stable:
        ranked=sorted(stability,key=lambda x:x.mean_importance,reverse=True)
        stable=tuple(x.name for x in ranked[:min(8,len(ranked))])
    final_rows=[_filter(f.values,stable) for f,_ in ds]
    final_model=model_factory().fit(final_rows,[y.up for _,y in ds])
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
    return TrainingReport(tuple(windows),stable,len(all_probs),accuracy,brier,snapshot)

def assert_snapshot_safe_for_simulation(snapshot,*,simulation_start_ms:int,bar_ms:int,purge_bars:int):
    required_gap=int(bar_ms)*int(purge_bars)
    if int(snapshot.trained_until)+required_gap>int(simulation_start_ms):
        raise ValueError('training window overlaps simulation window or purge gap')
    return True
