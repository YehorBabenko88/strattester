"""Synthetic engineering integration, explicitly NOT empirical OOS evidence."""
from dataclasses import replace
from hashlib import sha256
import socket
import pytest
import torch
from strattester.research.financial_contract import Instrument,Bar,Snapshot
from strattester.research.financial_snapshot import snapshot_bytes,load_snapshot
from strattester.research.financial_structural_model import StructuralConfig,build_structural_model
from strattester.research.financial_training import fit_structural
from strattester.research.financial_checkpoint import save_checkpoint,load_checkpoint
from strattester.research.financial_pipeline import feature_tracks, predict_snapshot


def synthetic_snapshot():
    rows=[]
    for symbol in ('BTCUSDT','ETHUSDT'):
        for tf in (60,120):
            for t in range(0,360,tf):
                rows.append(Bar(Instrument('bybit','linear',symbol),tf,t,t+tf,t+tf-1,t+tf,t+tf,360,
                                100.+t/60,'VERIFIED',True,True,1,'synthetic-fixture','a'*40))
    return Snapshot(tuple(rows),360,'synthetic-test-epoch',('synthetic-fixture',))


def test_snapshot_train_checkpoint_prediction_without_network_or_production_io(tmp_path,monkeypatch):
    def network_denied(*args,**kwargs):raise AssertionError('offline network side effect')
    monkeypatch.setattr(socket.socket,'connect',network_denied)
    monkeypatch.setattr(socket,'create_connection',network_denied)
    # Exercise training before loading so optimizer dependencies are also covered.
    snapshot=synthetic_snapshot();data=snapshot_bytes(snapshot);p=tmp_path/'snapshot.json';p.write_bytes(data)
    ds=sha256(data).hexdigest()
    verified=load_snapshot(p,ds,trusted_producers={'synthetic-fixture'},expected_coherence='synthetic-test-epoch')
    torch.manual_seed(2);model=build_structural_model(StructuralConfig(recycles=0))
    x,m,identities=feature_tracks(verified,timeframe_ns=60,config=model.config)
    fit_structural(model,x,torch.tensor([.01]),m,steps=2,seed=2)
    cp=tmp_path/'trained.json';ms=save_checkpoint(model,cp,dataset_sha256=ds,seed=2)
    reloaded,meta=load_checkpoint(cp,ms)
    pred=predict_snapshot(verified,reloaded,instrument=identities[0],timeframe_ns=60,horizon_ns=120,
                          model_sha256=ms,available_ns=361)
    assert pred.dataset_sha256==ds and pred.model_sha256==ms
    assert pred.origin_ns==360 and pred.available_ns==361 and pred.horizon_ns==120 and pred.scale>0
    x2,m2,_=feature_tracks(verified,timeframe_ns=120,config=model.config)
    assert x2.shape[2]==3


def test_misaligned_tracks_and_future_data_block_pipeline():
    snap=synthetic_snapshot();cfg=StructuralConfig()
    bad=replace(snap,bars=snap.bars[1:])
    with pytest.raises(ValueError,match='aligned'):feature_tracks(bad,timeframe_ns=60,config=cfg)
    row=replace(snap.bars[0],available_ns=361)
    with pytest.raises(ValueError):feature_tracks(replace(snap,bars=(row,*snap.bars[1:])),timeframe_ns=60,config=cfg)


def test_resource_admission_precedes_feature_allocation(monkeypatch):
    def reject(*a,**k):raise AssertionError('allocation reached')
    monkeypatch.setattr(torch,'tensor',reject)
    with pytest.raises(ValueError,match='budget'):
        feature_tracks(synthetic_snapshot(),timeframe_ns=60,config=StructuralConfig(max_tracks=1))


def test_prediction_cannot_relabel_the_trained_horizon():
    model=build_structural_model(StructuralConfig())
    with pytest.raises(ValueError,match='horizon'):
        predict_snapshot(synthetic_snapshot(),model,instrument=Instrument('bybit','linear','BTCUSDT'),
                         timeframe_ns=60,horizon_ns=60,model_sha256='a'*64,available_ns=361)


@pytest.mark.parametrize('kind',['unbound','wrong_digest','mutated'])
def test_prediction_cannot_claim_unverified_or_mutated_model_identity(tmp_path,kind):
    model=build_structural_model(StructuralConfig())
    path=tmp_path/'model.json';sha=save_checkpoint(model,path,dataset_sha256='a'*64,seed=0)
    if kind!='unbound':model,_=load_checkpoint(path,sha)
    if kind=='wrong_digest':sha='b'*64
    if kind=='mutated':
        with torch.no_grad():model.head.bias.add_(1.)
    with pytest.raises(ValueError,match='checkpoint|identity'):
        predict_snapshot(synthetic_snapshot(),model,instrument=Instrument('bybit','linear','BTCUSDT'),
                         timeframe_ns=60,horizon_ns=120,model_sha256=sha,available_ns=361)
