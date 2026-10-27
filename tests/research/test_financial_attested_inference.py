import runpy
from dataclasses import replace
from pathlib import Path
import socket
import pytest


def setup(tmp_path,**kwargs):
    b=runpy.run_path(str(Path(__file__).with_name('signed_export_fixture.py')))['bundle'](tmp_path,**kwargs)
    from strattester.research.financial_attested_inference import AttestedInferenceRequest
    request=AttestedInferenceRequest(tmp_path/'manifest.json',b['manifest_sha'],tmp_path/'snapshot.json',tmp_path/'checkpoint.json',b['checkpoint_sha'],tmp_path/'trust.json',b['trust_sha'],b['instrument'],b['tf'],b['tf']*2,b['snapshot'].origin_ns+10)
    return b,request


def test_signed_data_model_prediction_provenance_and_offline_backtest(tmp_path,monkeypatch):
    b,r=setup(tmp_path)
    from strattester.research.financial_attested_inference import run_attested_offline
    def denied(*a,**k):raise AssertionError('network/order side effect')
    monkeypatch.setattr(socket.socket,'connect',denied);monkeypatch.setattr(socket,'create_connection',denied)
    # Actual bounded learning, publication and verified reload on this signed
    # dataset, not an assertion of profitability from randomly initialized weights.
    import torch
    from hashlib import sha256
    from strattester.research.financial_signed_export import load_attested_export
    from strattester.research.financial_structural_model import StructuralConfig,build_structural_model
    from strattester.research.financial_pipeline import feature_tracks
    from strattester.research.financial_training import fit_structural
    from strattester.research.financial_checkpoint import save_checkpoint
    export=load_attested_export(manifest_path=r.manifest_path,manifest_sha256=r.manifest_sha256,snapshot_path=r.snapshot_path,
        trust_store_path=r.trust_store_path,trust_store_sha256=r.trust_store_sha256,policy=b['policy'],verifier=b['verifier'])
    model=build_structural_model(StructuralConfig(horizon_ns=r.horizon_ns,recycles=0))
    before={name:value.detach().clone() for name,value in model.state_dict().items()}
    x,mask,_=feature_tracks(export.snapshot,timeframe_ns=r.timeframe_ns,config=model.config)
    fit_structural(model,x,torch.tensor([.01]),mask,steps=1,seed=31)
    assert any(not torch.equal(before[name],value) for name,value in model.state_dict().items())
    trained_path=tmp_path/'trained.json'
    b['checkpoint_sha']=save_checkpoint(model,trained_path,dataset_sha256=export.provenance['snapshot_bytes_sha256'],seed=31)
    r=replace(r,checkpoint_path=trained_path,checkpoint_sha256=b['checkpoint_sha'])
    result=run_attested_offline(r,policy=b['policy'],verifier=b['verifier'])
    assert result.prediction.instrument==r.instrument and result.prediction.scale>0
    assert result.provenance['checkpoint_sha256']==b['checkpoint_sha']
    assert result.provenance['manifest_sha256']==b['manifest_sha']
    assert result.provenance['physical_g1']=='NOT_AUTHORIZED'
    from strattester.research.financial_evaluation import Trade,evaluate_ledger
    ledger=evaluate_ledger([Trade(r.instrument.symbol,result.prediction.available_ns,result.prediction.origin_ns+r.horizon_ns,.001,1)],fee_bps=2,slippage_bps=1)
    assert ledger['turnover']==2 and ledger['returns']==pytest.approx([.0004])

@pytest.mark.parametrize('symbol,market',[('BTCUSDT','linear'),('ETHUSDT','spot'),('SOLUSDT','linear'),('BTCUSD','inverse')])
@pytest.mark.parametrize('tf',[60_000_000_000,300_000_000_000,3600_000_000_000,86400_000_000_000])
def test_market_identity_and_fixed_duration_timeframe_matrix(tmp_path,symbol,market,tf):
    b,r=setup(tmp_path,symbol=symbol,market=market,tf=tf)
    from strattester.research.financial_attested_inference import run_attested_offline
    result=run_attested_offline(r,policy=b['policy'],verifier=b['verifier'])
    assert result.prediction.instrument==r.instrument and result.prediction.horizon_ns==2*tf


def test_aggregate_budget_rejects_before_checkpoint_model_allocation(tmp_path,monkeypatch):
    b,r=setup(tmp_path)
    import strattester.research.financial_attested_inference as bridge
    def denied(*a,**k):raise AssertionError('model load reached')
    monkeypatch.setattr(bridge,'load_checkpoint',denied)
    with pytest.raises(ValueError,match='budget'):bridge.run_attested_offline(r,policy=b['policy'],verifier=b['verifier'],max_work_bytes=1)


def test_cancellation_precedes_all_artifact_io(tmp_path):
    b,r=setup(tmp_path)
    from strattester.research.financial_attested_inference import run_attested_offline
    from strattester.research.financial_training import TrainingCancelled
    with pytest.raises(TrainingCancelled):run_attested_offline(r,policy=b['policy'],verifier=b['verifier'],cancel=lambda:True)


def test_late_availability_cannot_backdate_forecast_execution(tmp_path):
    b,r=setup(tmp_path)
    from strattester.research.financial_attested_inference import run_attested_offline
    with pytest.raises(ValueError):run_attested_offline(replace(r,available_ns=b['snapshot'].origin_ns+r.horizon_ns),policy=b['policy'],verifier=b['verifier'])


def test_prediction_cannot_be_available_before_signature_verification(tmp_path):
    b,r=setup(tmp_path)
    from strattester.research.financial_attested_inference import run_attested_offline
    with pytest.raises(ValueError,match='available'):
        run_attested_offline(replace(r,available_ns=b['snapshot'].origin_ns+1),policy=b['policy'],verifier=b['verifier'])


def test_signed_multi_market_export_preserves_target_identity_under_track_permutation(tmp_path):
    from hashlib import sha256
    from dataclasses import replace
    from strattester.research.financial_contract import Instrument
    from strattester.research.financial_snapshot import snapshot_bytes
    from strattester.research.financial_signed_export import MarketPartition
    from strattester.research.financial_attested_inference import run_attested_offline
    b,r=setup(tmp_path)
    other=Instrument('bybit','spot',r.instrument.symbol)
    extra=tuple(replace(bar,instrument=other,close=bar.close*1.2) for bar in b['snapshot'].bars)
    snapshot=replace(b['snapshot'],bars=(*b['snapshot'].bars,*extra))
    partition=MarketPartition('bybit','spot',r.instrument.symbol,r.timeframe_ns)
    policy=replace(b['policy'],partitions=(*b['policy'].partitions,partition))
    manifest=b['manifest'];manifest['partitions'].append(dict(exchange='bybit',market_type='spot',symbol=r.instrument.symbol,timeframe_ns=r.timeframe_ns))
    outputs=[]
    for bars in (snapshot.bars,(*extra,*b['snapshot'].bars)):
        current=replace(snapshot,bars=tuple(bars));data=snapshot_bytes(current);(tmp_path/'snapshot.json').write_bytes(data)
        manifest.update(snapshot_sha256=sha256(data).hexdigest(),snapshot_bytes=len(data),row_count=len(bars))
        request=replace(r,manifest_sha256=b['publish'](manifest),instrument=other)
        result=run_attested_offline(request,policy=policy,verifier=b['verifier'])
        assert result.prediction.instrument==other
        assert len(result.provenance['partitions'])==2
        outputs.append((result.prediction.mu,result.prediction.scale))
    assert outputs[0]==outputs[1]
