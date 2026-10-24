"""Typed Snapshot -> aligned historical tracks -> distribution boundary."""
from hashlib import sha256
import math
from .financial_contract import Prediction, integer, digest
from .financial_snapshot import snapshot_bytes


def feature_tracks(snapshot, *, timeframe_ns, config):
    import torch
    snapshot.validate();config.validate();integer(timeframe_ns,'timeframe_ns',1)
    groups={}
    for bar in snapshot.bars:
        if bar.timeframe_ns==timeframe_ns:groups.setdefault(bar.instrument,[]).append(bar)
    if not groups:raise ValueError('missing selected timeframe')
    identities=tuple(sorted(groups))
    times=tuple(b.candle_open_ns for b in groups[identities[0]])
    if any(tuple(b.candle_open_ns for b in rows)!=times for rows in groups.values()): raise ValueError('tracks must be exactly aligned')
    s,n=len(identities),len(times)
    if not 1<=s<=config.max_tracks or not 2<=n<=config.max_tokens or config.input_channels!=3:
        raise ValueError('feature allocation budget/config')
    if s*n*3*4*8>config.max_work_bytes:raise ValueError('feature byte budget')
    tracks=[]
    for identity in identities:
        logs=[math.log(b.close) for b in groups[identity]]
        returns=[0.,*(b-a for a,b in zip(logs,logs[1:]))]
        track=[]
        for i,r in enumerate(returns):
            window=returns[max(0,i-7):i+1];mu=sum(window)/len(window)
            volatility=math.sqrt(sum((v-mu)**2 for v in window)/len(window))
            track.append([r,mu,volatility])
        tracks.append(track)
    return torch.tensor([tracks],dtype=torch.float32),torch.ones((1,s,n),dtype=torch.bool),identities


def predict_snapshot(snapshot, model, *, instrument, timeframe_ns, horizon_ns, model_sha256, available_ns):
    import torch
    integer(horizon_ns,'horizon_ns',1);integer(available_ns,'available_ns');digest(model_sha256)
    if horizon_ns%timeframe_ns:raise ValueError('horizon must align to timeframe')
    x,mask,identities=feature_tracks(snapshot,timeframe_ns=timeframe_ns,config=model.config)
    if instrument not in identities:raise ValueError('missing target instrument')
    index=identities.index(instrument)
    order=[index,*[i for i in range(len(identities)) if i!=index]]
    parameter=next(model.parameters())
    x=x[:,order].to(device=parameter.device,dtype=parameter.dtype);mask=mask[:,order].to(parameter.device)
    previous=model.training
    try:
        model.eval()
        with torch.no_grad():mu,scale=model(x,mask)[0].tolist()
    finally:model.train(previous)
    prediction=Prediction(instrument,snapshot.origin_ns,available_ns,horizon_ns,mu,scale,
                          sha256(snapshot_bytes(snapshot)).hexdigest(),model_sha256)
    prediction.validate()
    return prediction
